#!/usr/bin/env python3
"""Generate, build, run, and compare the manifest-driven AAPG suite."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import yaml


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "suite_manifest.yaml"
WORK = ROOT / "work"
SUITE_WORK = WORK / "suites"
CENTRAL_LOG = WORK / "log"
CENTRAL_OBJDUMP = WORK / "objdump"
DUT_WORK = WORK / "dut"

REQUIRED_SECTIONS = {
    "switch-priv-modes",
    "priv-mode",
    "general",
    "isa-instruction-distribution",
    "float-rounding",
    "branch-control",
    "recursion-options",
    "access-sections",
    "user-functions",
    "i-cache",
    "d-cache",
    "exception-generation",
    "csr-sections",
    "data-hazards",
    "program-macro",
    "self-checking",
}


def load_manifest() -> dict:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="ascii"))
    if not isinstance(manifest, dict):
        raise ValueError("suite_manifest.yaml must contain a mapping")
    return manifest


def selected_suites(manifest: dict, names: list[str] | None) -> list[dict]:
    suites = manifest["suites"]
    if not names:
        return suites
    by_id = {item["id"]: item for item in suites}
    missing = sorted(set(names) - set(by_id))
    if missing:
        raise ValueError(f"Unknown suite(s): {', '.join(missing)}")
    return [by_id[name] for name in names]


def suite_dir(item: dict) -> Path:
    return SUITE_WORK / item["id"]


def display_command(command: Iterable[object]) -> str:
    return shlex.join(str(part) for part in command)


def run_command(
    command: list[object],
    *,
    cwd: Path = ROOT,
    timeout: int | None = None,
    stdout=None,
    stderr=None,
) -> subprocess.CompletedProcess:
    command = [str(part) for part in command]
    print(f"+ {display_command(command)}")
    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        check=True,
        stdout=stdout,
        stderr=stderr,
        text=stdout is None and stderr is None,
    )


def require_tools(names: Iterable[str]) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"Missing required tools: {', '.join(missing)}")


def validate_config(item: dict, config: dict, isa: str) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_SECTIONS - set(config)
    if missing:
        errors.append(f"missing sections: {', '.join(sorted(missing))}")

    general = config.get("general", {})
    if int(general.get("total_instructions", 0)) <= 0:
        errors.append("total_instructions must be positive")
    if general.get("code_start_address") not in (0x80000000, "0x80000000", 2147483648):
        errors.append("code_start_address must match the C-Class 0x80000000 reset target")

    mode = config.get("priv-mode", {}).get("mode")
    if mode not in {"m", "s", "u"}:
        errors.append("priv-mode.mode must be m, s, or u")

    distribution = config.get("isa-instruction-distribution", {})
    if not distribution or not any(float(value) > 0 for value in distribution.values()):
        errors.append("at least one ISA distribution weight must be positive")
    if any(float(value) < 0 for value in distribution.values()):
        errors.append("ISA distribution weights cannot be negative")
    if "z" not in isa.lower():
        enabled_z = [key for key, value in distribution.items() if ".z" in key and float(value) > 0]
        if enabled_z:
            errors.append(f"unsupported Z-extension weights enabled: {enabled_z}")

    hazards = config.get("data-hazards", {})
    for key in ("raw_prob", "war_prob", "waw_prob"):
        value = float(hazards.get(key, -1))
        if not 0.0 <= value <= 1.0:
            errors.append(f"{key} must be between 0.0 and 1.0")

    if item.get("self_checking") and int(item.get("programs", 0)) != 1:
        errors.append("AAPG self-checking supports exactly one program")
    if config.get("switch-priv-modes", {}).get("switch_modes") and item.get("self_checking"):
        errors.append("privilege switching and self-checking are mutually exclusive")
    return errors


def command_validate(manifest: dict, suites: list[dict]) -> None:
    all_errors: list[str] = []
    if manifest.get("suite_count") != 32 or len(manifest.get("suites", [])) != 32:
        all_errors.append("manifest must contain exactly 32 suites")
    ids = [item["id"] for item in manifest.get("suites", [])]
    if len(ids) != len(set(ids)):
        all_errors.append("suite IDs are not unique")

    for item in suites:
        path = ROOT / item["config"]
        if not path.is_file():
            all_errors.append(f"{item['id']}: missing {path}")
            continue
        try:
            config = yaml.safe_load(path.read_text(encoding="ascii"))
        except Exception as exc:  # pragma: no cover - parser includes useful detail
            all_errors.append(f"{item['id']}: YAML parse failed: {exc}")
            continue
        for error in validate_config(item, config, manifest["isa"]):
            all_errors.append(f"{item['id']}: {error}")

    if all_errors:
        raise RuntimeError("Configuration validation failed:\n  " + "\n  ".join(all_errors))
    print(f"PASS: validated {len(suites)} selected suite(s); manifest contains 32 suites")


def aapg_work_dir(item: dict) -> Path:
    """Return the standard AAPG setup/output directory for one isolated suite."""
    return suite_dir(item) / "work"


def command_setup(suites: list[dict]) -> None:
    require_tools(["aapg"])
    for item in suites:
        target = suite_dir(item)
        target.mkdir(parents=True, exist_ok=True)
        run_command(["aapg", "setup", "--setup_dir", "work"], cwd=target)
    CENTRAL_LOG.mkdir(parents=True, exist_ok=True)
    CENTRAL_OBJDUMP.mkdir(parents=True, exist_ok=True)


def remove_old_program_files(target: Path, ident: str) -> None:
    patterns = (f"{ident}*.S", f"{ident}*.ld", f"{ident}*.riscv", f"{ident}*.objdump")
    for pattern in patterns:
        for path in target.glob(pattern):
            if path.is_file():
                path.unlink()


def command_generate(suites: list[dict]) -> None:
    require_tools(["aapg"])
    for item in suites:
        target = suite_dir(item)
        runtime = aapg_work_dir(item)
        if not (runtime / "common" / "encoding.h").is_file():
            target.mkdir(parents=True, exist_ok=True)
            run_command(["aapg", "setup", "--setup_dir", "work"], cwd=target)
        remove_old_program_files(runtime / "asm", item["id"])
        command = [
            "aapg",
            "gen",
            "--config_file",
            ROOT / item["config"],
            "--asm_name",
            item["id"],
            "--setup_dir",
            "work",
            "--output_dir",
            "work",
            "--arch",
            "rv64",
            "--seed",
            item["seed"],
            "--num_programs",
            item["programs"],
        ]
        if item.get("self_checking"):
            command.append("--self_checking")
        run_command(command, cwd=target)
        sources = source_files(item)
        if len(sources) != int(item["programs"]):
            raise RuntimeError(f"{item['id']}: expected {item['programs']} generated programs, found {len(sources)}")
        print(f"PASS: {item['id']} generated {len(sources)} program(s), seed {item['seed']}")


def source_files(item: dict) -> list[Path]:
    asm_dir = aapg_work_dir(item) / "asm"
    return sorted(path for path in asm_dir.glob(f"{item['id']}*.S") if not path.name.endswith("_template.S"))


def command_build(manifest: dict, suites: list[dict]) -> None:
    require_tools(["riscv64-unknown-elf-gcc", "riscv64-unknown-elf-objdump"])
    CENTRAL_OBJDUMP.mkdir(parents=True, exist_ok=True)
    for item in suites:
        target = aapg_work_dir(item)
        sources = source_files(item)
        if not sources:
            raise RuntimeError(f"{item['id']}: no assembly found; run generation first")
        bin_dir = target / "bin"
        objdump_dir = target / "objdump"
        bin_dir.mkdir(exist_ok=True)
        objdump_dir.mkdir(exist_ok=True)
        crt = target / "common" / "crt.S"
        for source in sources:
            stem = source.stem
            linker = source.with_suffix(".ld")
            output = bin_dir / f"{stem}.riscv"
            if not linker.is_file() or not crt.is_file():
                raise RuntimeError(f"{item['id']}: missing {linker.name} or common/crt.S")
            run_command(
                [
                    "riscv64-unknown-elf-gcc",
                    f"-march={manifest['isa']}",
                    f"-mabi={manifest['abi']}",
                    "-DPREALLOCATE=1",
                    "-mcmodel=medany",
                    "-static",
                    "-std=gnu99",
                    "-O2",
                    "-fno-common",
                    "-fno-builtin-printf",
                    "-nostdlib",
                    "-nostartfiles",
                    "-I",
                    source.parent,
                    "-I",
                    target / "common",
                    source,
                    crt,
                    "-T",
                    linker,
                    "-lm",
                    "-lgcc",
                    "-o",
                    output,
                ]
            )
            objdump = objdump_dir / f"{stem}.objdump"
            with objdump.open("w", encoding="ascii") as handle:
                run_command(["riscv64-unknown-elf-objdump", "-D", output], stdout=handle)
            shutil.copy2(objdump, CENTRAL_OBJDUMP / f"{item['id']}__{stem}.objdump")
            print(f"PASS: built {output}")


def binary_files(item: dict) -> list[Path]:
    return sorted((aapg_work_dir(item) / "bin").glob(f"{item['id']}*.riscv"))


def command_spike(manifest: dict, suites: list[dict], timeout: int) -> None:
    require_tools(["spike"])
    CENTRAL_LOG.mkdir(parents=True, exist_ok=True)
    for item in suites:
        binaries = binary_files(item)
        if not binaries:
            raise RuntimeError(f"{item['id']}: no binary found; run build first")
        for binary in binaries:
            prefix = f"{item['id']}__{binary.stem}"
            execution_log = CENTRAL_LOG / f"{prefix}.log"
            with execution_log.open("w", encoding="ascii") as handle:
                run_command(
                    ["spike", "-l", f"--isa={manifest['isa']}", binary],
                    timeout=timeout,
                    stderr=handle,
                )
            dump = CENTRAL_LOG / f"{prefix}.dump"
            signature = CENTRAL_LOG / f"{prefix}.signature"
            run_command(
                [
                    "spike",
                    "--log-commits",
                    "--log",
                    dump,
                    f"--isa={manifest['isa']}",
                    f"+signature={signature}",
                    "+signature-granularity=4",
                    binary,
                ],
                timeout=timeout,
            )
            print(f"PASS: Spike logs written for {prefix}")


def command_dut(suites: list[dict], design_home: Path, timeout: int) -> None:
    require_tools(["elf2hex"])
    design_home = design_home.resolve()
    for required in ("out", "boot.MSB", "boot.LSB"):
        if not (design_home / required).is_file():
            raise RuntimeError(f"DESIGN_HOME is missing {required}: {design_home}")

    for item in suites:
        for binary in binary_files(item):
            prefix = f"{item['id']}__{binary.stem}"
            target = DUT_WORK / item["id"] / binary.stem
            target.mkdir(parents=True, exist_ok=True)
            for path in design_home.iterdir():
                destination = target / path.name
                if path.is_dir():
                    shutil.copytree(path, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(path, destination)
            code_mem = target / "code.mem"
            with code_mem.open("w", encoding="ascii") as handle:
                run_command(["elf2hex", "8", "4194304", binary, "2147483648"], stdout=handle)
            run_command([target / "out", "+rtldump"], cwd=target, timeout=timeout)
            rtl_dump = target / "rtl.dump"
            if not rtl_dump.is_file():
                raise RuntimeError(f"{prefix}: DUT did not create rtl.dump")
            shutil.copy2(rtl_dump, CENTRAL_LOG / f"{prefix}.rtl.dump")
            print(f"PASS: C-Class dump written for {prefix}")


CSR_ORDER = re.compile(r"c2_frm (0x[0-9a-fA-F]+) c1_fflags (0x[0-9a-fA-F]+)")
CSR_TRAILING_WRITE = re.compile(r" c[0-9]+_[^ ]+ 0x[0-9a-fA-F]+$")
CSR_ENCODING = re.compile(r"\(0x[0-9a-fA-F]{3}0[37][0-9a-fA-F]{3}\)")


def normalize_dump(lines: list[str], *, rtl: bool, trim_lines: int) -> list[str]:
    if rtl and trim_lines:
        lines = lines[:-trim_lines] if len(lines) >= trim_lines else []
    normalized = []
    for line in lines:
        line = CSR_ORDER.sub(r"c1_fflags \2 c2_frm \1", line.rstrip())
        if CSR_ENCODING.search(line):
            line = CSR_TRAILING_WRITE.sub("", line)
        normalized.append(line.lower())
    return normalized


def compare_one(prefix: str, trim_lines: int) -> bool:
    spike_dump = CENTRAL_LOG / f"{prefix}.dump"
    rtl_dump = CENTRAL_LOG / f"{prefix}.rtl.dump"
    if not spike_dump.is_file() or not rtl_dump.is_file():
        raise RuntimeError(f"{prefix}: missing Spike or RTL dump")
    spike_lines = normalize_dump(spike_dump.read_text(encoding="ascii", errors="replace").splitlines(), rtl=False, trim_lines=0)
    rtl_lines = normalize_dump(rtl_dump.read_text(encoding="ascii", errors="replace").splitlines(), rtl=True, trim_lines=trim_lines)
    diff = list(
        difflib.unified_diff(
            spike_lines,
            rtl_lines,
            fromfile=str(spike_dump),
            tofile=str(rtl_dump),
            lineterm="",
        )
    )
    diff_path = CENTRAL_LOG / f"{prefix}.diff"
    if diff:
        diff_path.write_text("\n".join(diff) + "\n", encoding="ascii")
        print(f"FAIL: {prefix}; see {diff_path}")
        return False
    if diff_path.exists():
        diff_path.unlink()
    print(f"PASS: {prefix}; Spike and C-Class match")
    return True


def command_compare(suites: list[dict], trim_lines: int) -> None:
    results = {}
    for item in suites:
        binaries = binary_files(item)
        for binary in binaries:
            prefix = f"{item['id']}__{binary.stem}"
            results[prefix] = compare_one(prefix, trim_lines)
    summary = {"passed": sum(results.values()), "failed": len(results) - sum(results.values()), "results": results}
    (WORK / "verification_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    if not all(results.values()):
        raise RuntimeError(f"{summary['failed']} Spike/C-Class comparison(s) failed")


def command_debug(manifest: dict, suites: list[dict], program: int) -> None:
    if len(suites) != 1:
        raise RuntimeError("Interactive Spike debug requires exactly one --suite")
    binaries = binary_files(suites[0])
    if not binaries:
        raise RuntimeError("No binary found; run build first")
    if not 0 <= program < len(binaries):
        raise RuntimeError(f"Program index must be between 0 and {len(binaries) - 1}")
    run_command(["spike", "-d", "--log-commits", f"--isa={manifest['isa']}", binaries[program]])


def command_toolcheck() -> None:
    tools = ["aapg", "riscv64-unknown-elf-gcc", "riscv64-unknown-elf-objdump", "spike", "elf2hex"]
    failed = False
    for name in tools:
        location = shutil.which(name)
        print(f"{name:32} {location or 'MISSING'}")
        failed = failed or location is None
    if failed:
        raise RuntimeError("One or more required tools are missing")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["toolcheck", "validate", "setup", "generate", "build", "spike", "dut", "compare", "verify", "debug"])
    parser.add_argument("--suite", action="append", help="Exact suite ID; repeat to select several. Default: all")
    parser.add_argument("--spike-timeout", type=int, default=int(os.environ.get("SPIKE_TIMEOUT", "60")))
    parser.add_argument("--dut-timeout", type=int, default=int(os.environ.get("DUT_TIMEOUT", "600")))
    parser.add_argument("--rtl-skip-lines", type=int, default=int(os.environ.get("RTL_SKIP_LINES", "4")))
    parser.add_argument("--design-home", type=Path, default=Path(os.environ["DESIGN_HOME"]) if os.environ.get("DESIGN_HOME") else None)
    parser.add_argument("--program", type=int, default=0, help="Zero-based program index for interactive debug")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "toolcheck":
            command_toolcheck()
            return 0
        manifest = load_manifest()
        suites = selected_suites(manifest, args.suite)
        if args.command == "validate":
            command_validate(manifest, suites)
        elif args.command == "setup":
            command_setup(suites)
        elif args.command == "generate":
            command_validate(manifest, suites)
            command_generate(suites)
        elif args.command == "build":
            command_build(manifest, suites)
        elif args.command == "spike":
            command_spike(manifest, suites, args.spike_timeout)
        elif args.command == "dut":
            if args.design_home is None:
                raise RuntimeError("Set DESIGN_HOME or pass --design-home")
            command_dut(suites, args.design_home, args.dut_timeout)
        elif args.command == "compare":
            command_compare(suites, args.rtl_skip_lines)
        elif args.command == "verify":
            if args.design_home is None:
                raise RuntimeError("Set DESIGN_HOME or pass --design-home")
            command_validate(manifest, suites)
            command_generate(suites)
            command_build(manifest, suites)
            command_spike(manifest, suites, args.spike_timeout)
            command_dut(suites, args.design_home, args.dut_timeout)
            command_compare(suites, args.rtl_skip_lines)
        elif args.command == "debug":
            command_debug(manifest, suites, args.program)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
