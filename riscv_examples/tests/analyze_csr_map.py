#!/usr/bin/env python3
"""Classify every generated CSR map probe as legal or illegal.

The analyzer uses the generated disassembly to map each probe PC to its CSR
address and operation. A probe that retires appears in the commit dump; an
illegal CSR access traps before retirement and therefore does not.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

EXPECTED_PROBES = 4096 * 4
FUNCT3_NAMES = {
    0b010: "csrrs_zero",
    0b011: "csrrc_zero",
    0b110: "csrrsi_zero",
    0b111: "csrrci_zero",
}

LABEL_RE = re.compile(r"^[0-9a-f]+ <csr_address_([0-9a-f]{3})>:$")
INSTRUCTION_RE = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+")
DUMP_PC_RE = re.compile(r"core\s+\d+:\s+\d+\s+0x([0-9a-fA-F]+)\s+\(")


@dataclass(frozen=True)
class Probe:
    csr: int
    operation: str
    pc: int
    instruction: int


def parse_disassembly(path: Path) -> list[Probe]:
    probes: list[Probe] = []
    current_csr: int | None = None
    current_probe_count = 0

    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        label_match = LABEL_RE.match(line.strip())
        if label_match:
            current_csr = int(label_match.group(1), 16)
            current_probe_count = 0
            continue

        if current_csr is None or current_probe_count == 4:
            continue

        instruction_match = INSTRUCTION_RE.match(line)
        if not instruction_match:
            continue

        pc = int(instruction_match.group(1), 16)
        instruction = int(instruction_match.group(2), 16)
        opcode = instruction & 0x7F
        csr = (instruction >> 20) & 0xFFF
        operand_field = (instruction >> 15) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rd = (instruction >> 7) & 0x1F

        if (
            opcode != 0x73
            or csr != current_csr
            or operand_field != 0
            or rd != 0
            or funct3 not in FUNCT3_NAMES
        ):
            continue

        probes.append(
            Probe(
                csr=csr,
                operation=FUNCT3_NAMES[funct3],
                pc=pc,
                instruction=instruction,
            )
        )
        current_probe_count += 1

    if len(probes) != EXPECTED_PROBES:
        raise RuntimeError(
            f"Found {len(probes):,} map probes; expected {EXPECTED_PROBES:,}"
        )
    if len({probe.pc for probe in probes}) != EXPECTED_PROBES:
        raise RuntimeError("Probe PCs are not unique")
    return probes


def parse_retired_pcs(path: Path) -> set[int]:
    retired: set[int] = set()
    with path.open("r", encoding="ascii", errors="replace") as stream:
        for line in stream:
            match = DUMP_PC_RE.search(line)
            if match:
                retired.add(int(match.group(1), 16))
    return retired


def status(probe: Probe, retired_pcs: set[int]) -> str:
    return "legal" if probe.pc in retired_pcs else "illegal"


def write_report(
    path: Path,
    probes: list[Probe],
    spike_pcs: set[int],
    rtl_pcs: set[int] | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="ascii") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "csr",
                "operation",
                "pc",
                "instruction",
                "spike_outcome",
                "rtl_outcome",
                "outcome_match",
            )
        )
        for probe in probes:
            spike_status = status(probe, spike_pcs)
            rtl_status = "not_provided"
            match = "not_provided"
            if rtl_pcs is not None:
                rtl_status = status(probe, rtl_pcs)
                match = str(spike_status == rtl_status).lower()
            writer.writerow(
                (
                    f"0x{probe.csr:03x}",
                    probe.operation,
                    f"0x{probe.pc:016x}",
                    f"0x{probe.instruction:08x}",
                    spike_status,
                    rtl_status,
                    match,
                )
            )


def print_summary(
    probes: list[Probe],
    spike_pcs: set[int],
    rtl_pcs: set[int] | None,
) -> None:
    spike_legal = sum(status(probe, spike_pcs) == "legal" for probe in probes)
    print(f"Probes analyzed: {len(probes):,}")
    print(f"Spike legal:     {spike_legal:,}")
    print(f"Spike illegal:   {len(probes) - spike_legal:,}")

    if rtl_pcs is None:
        return

    rtl_legal = sum(status(probe, rtl_pcs) == "legal" for probe in probes)
    mismatches = [
        probe
        for probe in probes
        if status(probe, spike_pcs) != status(probe, rtl_pcs)
    ]
    mismatch_addresses = sorted({probe.csr for probe in mismatches})
    directions = Counter(
        (status(probe, spike_pcs), status(probe, rtl_pcs))
        for probe in mismatches
    )
    print(f"RTL legal:       {rtl_legal:,}")
    print(f"RTL illegal:     {len(probes) - rtl_legal:,}")
    print(f"Outcome mismatches: {len(mismatches):,}")
    print(f"CSR addresses with mismatches: {len(mismatch_addresses):,}")
    for (spike_status, rtl_status), count in sorted(directions.items()):
        print(f"  Spike {spike_status}, RTL {rtl_status}: {count:,}")
    if mismatches:
        first = mismatches[0]
        print(
            "First mismatch:  "
            f"CSR 0x{first.csr:03x}, {first.operation}, "
            f"Spike={status(first, spike_pcs)}, RTL={status(first, rtl_pcs)}"
        )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify legal/illegal outcomes in generated CSR map dumps."
    )
    parser.add_argument("--disassembly", type=Path, required=True)
    parser.add_argument("--spike-dump", type=Path, required=True)
    parser.add_argument("--rtl-dump", type=Path)
    parser.add_argument("--output", type=Path, default=Path("csr_map_outcomes.csv"))
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    probes = parse_disassembly(arguments.disassembly)
    spike_pcs = parse_retired_pcs(arguments.spike_dump)
    rtl_pcs = (
        parse_retired_pcs(arguments.rtl_dump)
        if arguments.rtl_dump is not None
        else None
    )
    write_report(arguments.output, probes, spike_pcs, rtl_pcs)
    print_summary(probes, spike_pcs, rtl_pcs)
    print(f"Report: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
