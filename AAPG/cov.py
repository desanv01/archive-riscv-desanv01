#!/usr/bin/env python3
"""Build UCIS XML and an interactive instruction histogram from AAPG traces."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent
MANIFEST_DEFAULT = ROOT / "suite_manifest.yaml"
LOG_DEFAULT = ROOT / "work" / "log"
OBJDUMP_DEFAULT = ROOT / "work" / "objdump"
REPORT_DEFAULT = ROOT / "coverage"
XML_DEFAULT = ROOT / "cov.xml"

DYNAMIC_RE = re.compile(
    r"\bcore\s+\d+:\s+(?:\d+\s+)?0x[0-9a-fA-F]+\s+"
    r"\(0x[0-9a-fA-F]+\)\s+([A-Za-z][A-Za-z0-9_.]*)"
)
OBJDUMP_RE = re.compile(
    r"^\s*[0-9a-fA-F]+:\s+(?:[0-9a-fA-F]{2}\s+|[0-9a-fA-F]+\s+)"
    r"([A-Za-z][A-Za-z0-9_.]*)\b"
)

M_INSTRUCTIONS = re.compile(r"^(mul|div|divu|rem|remu)(w|uw|h|hsu|hu)?$")
SYSTEM_INSTRUCTIONS = {
    "ecall",
    "ebreak",
    "uret",
    "sret",
    "mret",
    "dret",
    "wfi",
    "sfence.vma",
    "unimp",
}
EXTENSIONS = ("I", "M", "A", "F", "D", "C", "SYSTEM", "FENCE")


def normalize_mnemonic(value: str) -> str:
    return value.strip().lower().rstrip(",")


def classify_instruction(mnemonic: str) -> str:
    mnemonic = normalize_mnemonic(mnemonic)
    base = re.sub(r"\.(aqrl|aq|rl)$", "", mnemonic)
    if base.startswith("c."):
        return "C"
    if base.startswith(("amo", "lr.", "sc.")):
        return "A"
    if M_INSTRUCTIONS.match(base):
        return "M"
    if base.startswith(("fld", "fsd")) or (base.startswith("f") and ".d" in base):
        return "D"
    if base.startswith(("flw", "fsw")) or base.startswith("f"):
        return "F"
    if base.startswith("csr") or base in SYSTEM_INSTRUCTIONS:
        return "SYSTEM"
    if base.startswith("fence"):
        return "FENCE"
    return "I"


def parse_trace(path: Path, source: str) -> Counter[str]:
    pattern = DYNAMIC_RE if source == "dynamic" else OBJDUMP_RE
    counts: Counter[str] = Counter()
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            counts[normalize_mnemonic(match.group(1))] += 1
    return counts


def split_artifact_name(path: Path) -> tuple[str, str]:
    stem = path.name
    for suffix in (".objdump", ".log"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    if "__" not in stem:
        return stem, stem
    return tuple(stem.split("__", 1))  # type: ignore[return-value]


def load_manifest(path: Path) -> dict:
    manifest = yaml.safe_load(path.read_text(encoding="ascii"))
    if manifest.get("suite_count") != 32 or len(manifest.get("suites", [])) != 32:
        raise ValueError("coverage requires the approved 32-suite manifest")
    return manifest


def gather_records(manifest: dict, log_dir: Path, objdump_dir: Path) -> tuple[list[dict], dict]:
    suite_ids = {item["id"] for item in manifest["suites"]}
    files = [(path, "dynamic") for path in sorted(log_dir.glob("*.log"))]
    files += [(path, "static") for path in sorted(objdump_dir.glob("*.objdump"))]
    records: list[dict] = []
    parsed_files: list[dict] = []
    for path, source in files:
        suite_id, program = split_artifact_name(path)
        if suite_id not in suite_ids:
            continue
        counts = parse_trace(path, source)
        parsed_files.append(
            {
                "suite": suite_id,
                "program": program,
                "source": source,
                "file": str(path),
                "instruction_count": sum(counts.values()),
                "unique_mnemonics": len(counts),
            }
        )
        for mnemonic, count in sorted(counts.items()):
            records.append(
                {
                    "suite": suite_id,
                    "program": program,
                    "source": source,
                    "extension": classify_instruction(mnemonic),
                    "mnemonic": mnemonic,
                    "count": count,
                }
            )

    dynamic_suites = {record["suite"] for record in records if record["source"] == "dynamic"}
    missing = [item["id"] for item in manifest["suites"] if item["id"] not in dynamic_suites]
    metadata = {
        "parsed_files": parsed_files,
        "dynamic_suites": sorted(dynamic_suites),
        "missing_dynamic_suites": missing,
    }
    return records, metadata


def aggregate(records: list[dict], *, source: str = "dynamic") -> tuple[dict[str, Counter], dict[str, Counter], Counter]:
    instructions: dict[str, Counter] = defaultdict(Counter)
    extensions: dict[str, Counter] = defaultdict(Counter)
    overall: Counter = Counter()
    for record in records:
        if record["source"] != source:
            continue
        instructions[record["suite"]][record["mnemonic"]] += record["count"]
        extensions[record["suite"]][record["extension"]] += record["count"]
        overall[record["mnemonic"]] += record["count"]
    return instructions, extensions, overall


def add_options(parent: ET.Element, *, at_least: int = 1) -> None:
    ET.SubElement(
        parent,
        "options",
        {
            "weight": "1",
            "goal": "100",
            "at_least": str(at_least),
            "auto_bin_max": "4096",
            "detect_overlap": "false",
        },
    )


def add_bin(parent: ET.Element, name: str, count: int, key: int) -> None:
    bin_node = ET.SubElement(parent, "coverpointBin", {"name": name, "type": "bins", "key": str(key)})
    range_node = ET.SubElement(bin_node, "range", {"from": "-1", "to": "-1"})
    ET.SubElement(range_node, "contents", {"coverageCount": str(int(count))})


def write_ucis(path: Path, manifest: dict, records: list[dict], metadata: dict) -> None:
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    root = ET.Element(
        "UCIS",
        {
            "xmlns:ucis": "http://www.w3.org/2001/XMLSchema-instance",
            "writtenBy": os.environ.get("USER", os.environ.get("USERNAME", "aapg")),
            "writtenTime": now,
            "ucisVersion": "1.0",
        },
    )
    ET.SubElement(root, "sourceFiles", {"fileName": str(MANIFEST_DEFAULT), "id": "1"})
    ET.SubElement(
        root,
        "historyNodes",
        {
            "historyNodeId": "0",
            "logicalName": "AAPG instruction coverage",
            "physicalName": path.name,
            "kind": "HistoryNodeKind.TEST",
            "testStatus": "true",
            "simtime": "0.0",
            "timeunit": "ns",
            "runCwd": str(ROOT),
            "cpuTime": "0.0",
            "seed": "0",
            "cmd": "python3 cov.py",
            "args": "",
            "compulsory": "0",
            "date": now,
            "userName": os.environ.get("USER", "user"),
            "cost": "0.0",
            "toolCategory": "UCIS:simulator",
            "ucisVersion": "1.0",
            "vendorId": "AAPG",
            "vendorTool": "cov.py",
            "vendorToolVersion": "1.0",
        },
    )
    instance = ET.SubElement(root, "instanceCoverages", {"name": "aapg_suite", "key": "0", "instanceId": "0", "moduleName": "aapg"})
    ET.SubElement(instance, "id", {"file": "1", "line": "1", "inlineCount": "1"})
    coverage = ET.SubElement(instance, "covergroupCoverage")
    group = ET.SubElement(coverage, "cgInstance", {"name": "AAPGInstructionCoverage", "key": "0"})
    ET.SubElement(group, "options", {"weight": "1", "goal": "100", "at_least": "1", "per_instance": "true", "merge_instances": "true"})
    group_id = ET.SubElement(group, "cgId", {"cgName": "AAPGInstructionCoverage", "moduleName": "AAPGInstructionCoverage"})
    ET.SubElement(group_id, "cginstSourceId", {"file": "1", "line": "1", "inlineCount": "1"})
    ET.SubElement(group_id, "cgSourceId", {"file": "1", "line": "1", "inlineCount": "1"})

    instructions, extensions, overall = aggregate(records)
    status = ET.SubElement(group, "coverpoint", {"name": "suite_execution_status", "key": "0"})
    add_options(status)
    dynamic_suites = set(metadata["dynamic_suites"])
    for index, item in enumerate(manifest["suites"]):
        add_bin(status, item["id"], 1 if item["id"] in dynamic_suites else 0, index)

    overall_point = ET.SubElement(group, "coverpoint", {"name": "all_executed_instructions", "key": "1"})
    add_options(overall_point)
    if overall:
        for index, (mnemonic, count) in enumerate(sorted(overall.items())):
            add_bin(overall_point, mnemonic, count, index)
    else:
        add_bin(overall_point, "no_dynamic_logs", 0, 0)

    key = 2
    for item in manifest["suites"]:
        suite_id = item["id"]
        point = ET.SubElement(group, "coverpoint", {"name": f"{suite_id}_instructions", "key": str(key)})
        add_options(point)
        if instructions[suite_id]:
            for index, (mnemonic, count) in enumerate(sorted(instructions[suite_id].items())):
                add_bin(point, mnemonic, count, index)
        else:
            add_bin(point, "no_dynamic_log", 0, 0)
        key += 1

        ext_point = ET.SubElement(group, "coverpoint", {"name": f"{suite_id}_extensions", "key": str(key)})
        add_options(ext_point)
        for index, extension in enumerate(EXTENSIONS):
            add_bin(ext_point, extension, extensions[suite_id][extension], index)
        key += 1

    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=False)


def write_csv(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ("suite", "program", "source", "extension", "mnemonic", "count")
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


def build_summary(manifest: dict, records: list[dict], metadata: dict) -> dict:
    by_source = Counter()
    by_extension = Counter()
    by_suite = Counter()
    for record in records:
        by_source[record["source"]] += record["count"]
        if record["source"] == "dynamic":
            by_extension[record["extension"]] += record["count"]
            by_suite[record["suite"]] += record["count"]
    return {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "suite_count": manifest["suite_count"],
        "suites_with_dynamic_logs": len(metadata["dynamic_suites"]),
        "missing_dynamic_suites": metadata["missing_dynamic_suites"],
        "instruction_totals_by_source": dict(sorted(by_source.items())),
        "dynamic_instruction_totals_by_extension": dict(sorted(by_extension.items())),
        "dynamic_instruction_totals_by_suite": dict(sorted(by_suite.items())),
        "parsed_files": metadata["parsed_files"],
    }


def write_histogram(path: Path, manifest: dict, records: list[dict], summary: dict) -> None:
    payload = json.dumps({"records": records, "suites": manifest["suites"], "summary": summary}, separators=(",", ":"))
    document = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AAPG Instruction Histogram</title>
<style>
:root{color-scheme:light;--ink:#17202a;--muted:#65717e;--line:#d8dee5;--panel:#f5f7f9;--blue:#1769aa;--green:#16835b;--amber:#b45f06}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;color:var(--ink);background:#fff}header{padding:18px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:16px}h1{font-size:21px;margin:0;letter-spacing:0}.meta{color:var(--muted)}main{padding:18px 24px}.controls{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px;margin-bottom:16px}.field{display:flex;flex-direction:column;gap:5px}.field label{font-size:12px;font-weight:650;color:var(--muted)}select,input,button{height:36px;border:1px solid #b8c1ca;border-radius:5px;background:#fff;color:var(--ink);padding:0 10px}button{cursor:pointer;font-weight:650}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px}.stat{border-left:4px solid var(--blue);background:var(--panel);padding:10px 12px;min-height:62px}.stat strong{display:block;font-size:20px}.stat span{color:var(--muted);font-size:12px}.chart{border-top:1px solid var(--line)}.row{display:grid;grid-template-columns:minmax(120px,210px) minmax(180px,1fr) 90px 70px;gap:10px;align-items:center;min-height:36px;border-bottom:1px solid #edf0f3}.name{font-family:ui-monospace,monospace;overflow:hidden;text-overflow:ellipsis}.track{height:20px;background:#edf1f4;position:relative}.bar{height:100%;min-width:1px;background:var(--blue)}.count{text-align:right;font-variant-numeric:tabular-nums}.ext{font-size:12px;color:var(--muted)}.empty{padding:40px 0;color:var(--muted);text-align:center}@media(max-width:800px){.controls,.stats{grid-template-columns:1fr 1fr}.row{grid-template-columns:110px 1fr 65px}.ext{display:none}}@media(max-width:520px){.controls,.stats{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><div><h1>AAPG Instruction Histogram</h1><div class="meta" id="generated"></div></div><button id="export">Export filtered CSV</button></header>
<main>
<section class="controls">
  <div class="field"><label for="suite">YAML configuration</label><select id="suite"></select></div>
  <div class="field"><label for="source">Count source</label><select id="source"><option value="dynamic">Dynamic Spike log</option><option value="static">Static objdump</option></select></div>
  <div class="field"><label for="extension">ISA extension</label><select id="extension"></select></div>
  <div class="field"><label for="search">Mnemonic filter</label><input id="search" placeholder="add, amo, fdiv..."></div>
</section>
<section class="stats"><div class="stat"><strong id="total">0</strong><span>instructions</span></div><div class="stat"><strong id="unique">0</strong><span>unique mnemonics</span></div><div class="stat"><strong id="suiteCount">0</strong><span>configs represented</span></div><div class="stat"><strong id="fileCount">0</strong><span>trace files parsed</span></div></section>
<section class="chart" id="chart"></section>
</main>
<script>
const DATA=__PAYLOAD__;
const suite=document.querySelector('#suite'),source=document.querySelector('#source'),extension=document.querySelector('#extension'),search=document.querySelector('#search'),chart=document.querySelector('#chart');
document.querySelector('#generated').textContent=`Generated ${DATA.summary.generated_at}; ${DATA.summary.suites_with_dynamic_logs}/${DATA.summary.suite_count} configs have Spike logs`;
suite.innerHTML='<option value="all">All configurations</option>'+DATA.suites.map(s=>`<option value="${s.id}">${s.id}</option>`).join('');
const extensions=[...new Set(DATA.records.map(r=>r.extension))].sort();extension.innerHTML='<option value="all">All extensions</option>'+extensions.map(v=>`<option>${v}</option>`).join('');
function filtered(){const q=search.value.trim().toLowerCase();return DATA.records.filter(r=>(suite.value==='all'||r.suite===suite.value)&&r.source===source.value&&(extension.value==='all'||r.extension===extension.value)&&(!q||r.mnemonic.includes(q)));}
function aggregate(rows){const map=new Map();for(const r of rows){const key=r.extension+'|'+r.mnemonic;const old=map.get(key)||{extension:r.extension,mnemonic:r.mnemonic,count:0};old.count+=r.count;map.set(key,old)}return [...map.values()].sort((a,b)=>b.count-a.count||a.mnemonic.localeCompare(b.mnemonic));}
function render(){const raw=filtered(),rows=aggregate(raw),max=Math.max(1,...rows.map(r=>r.count));document.querySelector('#total').textContent=rows.reduce((n,r)=>n+r.count,0).toLocaleString();document.querySelector('#unique').textContent=rows.length.toLocaleString();document.querySelector('#suiteCount').textContent=new Set(raw.map(r=>r.suite)).size;document.querySelector('#fileCount').textContent=DATA.summary.parsed_files.filter(f=>f.source===source.value&&(suite.value==='all'||f.suite===suite.value)).length;if(!rows.length){chart.innerHTML='<div class="empty">No instructions match the current filters.</div>';return}chart.innerHTML=rows.map(r=>`<div class="row" title="${r.mnemonic}: ${r.count}"><div class="name">${r.mnemonic}</div><div class="track"><div class="bar" style="width:${100*r.count/max}%"></div></div><div class="count">${r.count.toLocaleString()}</div><div class="ext">${r.extension}</div></div>`).join('');}
for(const el of [suite,source,extension,search])el.addEventListener(el===search?'input':'change',render);
document.querySelector('#export').addEventListener('click',()=>{const rows=filtered();const lines=['suite,program,source,extension,mnemonic,count',...rows.map(r=>[r.suite,r.program,r.source,r.extension,r.mnemonic,r.count].join(','))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'}));a.download='aapg_filtered_coverage.csv';a.click();URL.revokeObjectURL(a.href)});render();
</script>
</body></html>""".replace("__PAYLOAD__", payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    parser.add_argument("--log-dir", type=Path, default=LOG_DEFAULT)
    parser.add_argument("--objdump-dir", type=Path, default=OBJDUMP_DEFAULT)
    parser.add_argument("--output", type=Path, default=XML_DEFAULT)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--allow-empty", action="store_true", help="Create structurally valid reports before traces exist")
    parser.add_argument("--require-all", action="store_true", help="Fail unless all 32 configs have dynamic logs")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        manifest = load_manifest(args.manifest)
        records, metadata = gather_records(manifest, args.log_dir, args.objdump_dir)
        if not records and not args.allow_empty:
            raise RuntimeError(f"no Spike logs or objdumps found under {args.log_dir.parent}")
        if args.require_all and metadata["missing_dynamic_suites"]:
            raise RuntimeError(f"missing dynamic logs for {len(metadata['missing_dynamic_suites'])} suite(s)")
        summary = build_summary(manifest, records, metadata)
        write_ucis(args.output, manifest, records, metadata)
        write_csv(args.report_dir / "instruction_counts.csv", records)
        (args.report_dir / "coverage_summary.json").parent.mkdir(parents=True, exist_ok=True)
        (args.report_dir / "coverage_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
        write_histogram(args.report_dir / "histogram.html", manifest, records, summary)
        print(f"Wrote UCIS coverage: {args.output}")
        print(f"Wrote interactive histogram: {args.report_dir / 'histogram.html'}")
        print(f"Dynamic config coverage: {summary['suites_with_dynamic_logs']}/{summary['suite_count']}")
        if metadata["missing_dynamic_suites"]:
            print("Missing dynamic logs: " + ", ".join(metadata["missing_dynamic_suites"]))
    except (OSError, RuntimeError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
