#!/usr/bin/env python3
"""Generate safe, machine-mode CSR and MSIP verification programs.

The CSR instruction encoding space contains 25,165,824 combinations before
register data values are considered.  The generated assembly therefore uses:

* every one of the 4,096 CSR addresses with all four non-writing read forms;
* directed semantic checks for all six Zicsr instructions on ``mscratch``;
* controlled illegal-access checks with a trap handler that advances ``mepc``;
* an optional gzip CSV containing every CSR instruction-field combination.

Writes to every CSR address are deliberately not executed.  Doing so can
disable ISA extensions, redirect traps, alter interrupt state, or lock PMP.
"""

from __future__ import annotations

import argparse
import csv
import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TextIO

CSR_COUNT = 1 << 12
GPR_FIELD_COUNT = 1 << 5
REGISTER_FORM_COUNT = CSR_COUNT * 3 * GPR_FIELD_COUNT * GPR_FIELD_COUNT
IMMEDIATE_FORM_COUNT = CSR_COUNT * 3 * GPR_FIELD_COUNT * GPR_FIELD_COUNT
ENCODING_COUNT = REGISTER_FORM_COUNT + IMMEDIATE_FORM_COUNT

SYSTEM_OPCODE = 0x73


@dataclass(frozen=True)
class CsrOperation:
    name: str
    funct3: int
    immediate: bool
    read_suppressed_by_rd_zero: bool
    write_suppressed_by_operand_zero: bool


OPERATIONS = (
    CsrOperation("csrrw", 0b001, False, True, False),
    CsrOperation("csrrs", 0b010, False, False, True),
    CsrOperation("csrrc", 0b011, False, False, True),
    CsrOperation("csrrwi", 0b101, True, True, False),
    CsrOperation("csrrsi", 0b110, True, False, True),
    CsrOperation("csrrci", 0b111, True, False, True),
)

SAFE_READ_OPERATIONS = tuple(
    operation
    for operation in OPERATIONS
    if operation.name in {"csrrs", "csrrc", "csrrsi", "csrrci"}
)


def encode_csr(csr: int, funct3: int, rd: int, operand_field: int) -> int:
    """Encode one 32-bit Zicsr instruction."""
    if not 0 <= csr < CSR_COUNT:
        raise ValueError(f"CSR address out of range: {csr}")
    if not 0 <= rd < GPR_FIELD_COUNT:
        raise ValueError(f"rd out of range: {rd}")
    if not 0 <= operand_field < GPR_FIELD_COUNT:
        raise ValueError(f"operand field out of range: {operand_field}")
    return (
        (csr << 20)
        | (operand_field << 15)
        | (funct3 << 12)
        | (rd << 7)
        | SYSTEM_OPCODE
    )


def access_flags(operation: CsrOperation, rd: int, operand_field: int) -> tuple[bool, bool]:
    reads = not (operation.read_suppressed_by_rd_zero and rd == 0)
    writes = not (
        operation.write_suppressed_by_operand_zero and operand_field == 0
    )
    return reads, writes


def iter_encoding_rows() -> Iterator[tuple[str, ...]]:
    """Yield all 25,165,824 instruction-field combinations."""
    for csr in range(CSR_COUNT):
        privilege = (csr >> 8) & 0b11
        convention_read_only = ((csr >> 10) & 0b11) == 0b11
        for operation in OPERATIONS:
            operand_kind = "uimm" if operation.immediate else "rs1"
            for rd in range(GPR_FIELD_COUNT):
                for operand_field in range(GPR_FIELD_COUNT):
                    reads, writes = access_flags(operation, rd, operand_field)
                    instruction = encode_csr(
                        csr, operation.funct3, rd, operand_field
                    )
                    yield (
                        f"0x{csr:03x}",
                        str(privilege),
                        str(int(convention_read_only)),
                        operation.name,
                        str(rd),
                        operand_kind,
                        str(operand_field),
                        str(int(reads)),
                        str(int(writes)),
                        f"0x{instruction:08x}",
                    )


def write_encoding_manifest(path: Path) -> None:
    """Stream the complete encoding matrix to a compressed CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="ascii") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "csr",
                "minimum_privilege_encoding",
                "convention_read_only",
                "operation",
                "rd",
                "operand_kind",
                "operand_field",
                "reads_csr",
                "writes_csr",
                "instruction",
            )
        )
        writer.writerows(iter_encoding_rows())


def check_block(register: str, expected: int, test_number: int) -> list[str]:
    return [
        f"  li TESTNUM, {test_number}",
        f"  li t4, 0x{expected:016x}",
        f"  bne {register}, t4, fail",
    ]


def render_csr_assembly() -> str:
    lines = [
        '#include "riscv_test.h"',
        '#include "test_macros.h"',
        "",
        "  .option norelax",
        "RVTEST_RV64M",
        "RVTEST_CODE_BEGIN",
        "",
        "  .option norvc",
        "  .align 2",
        "",
        "  # s0 counts recovered illegal-instruction traps.",
        "  # s1 identifies the current CSR address during the full map.",
        "  li s0, 0",
        "  li s1, 0",
        "",
        "  # Preserve mscratch, the safe writable CSR used by semantic tests.",
        "  csrr s3, mscratch",
        "",
        "csr_csrrw:",
        "  li TESTNUM, 2",
        "  csrw mscratch, zero",
        "  li t0, 0x0123456789abcdef",
        "  csrrw t1, mscratch, t0",
        "  bnez t1, fail",
        "  csrr t2, mscratch",
    ]
    lines.extend(check_block("t2", 0x0123456789ABCDEF, 2))
    lines.extend(
        [
            "",
            "csr_csrrs:",
            "  li TESTNUM, 3",
            "  li t0, 0x10",
            "  csrw mscratch, t0",
            "  li t2, 0x05",
            "  csrrs t1, mscratch, t2",
        ]
    )
    lines.extend(check_block("t1", 0x10, 3))
    lines.extend(["  csrr t1, mscratch"])
    lines.extend(check_block("t1", 0x15, 3))
    lines.extend(
        [
            "",
            "csr_csrrc:",
            "  li TESTNUM, 4",
            "  li t0, 0x1f",
            "  csrw mscratch, t0",
            "  li t2, 0x05",
            "  csrrc t1, mscratch, t2",
        ]
    )
    lines.extend(check_block("t1", 0x1F, 4))
    lines.extend(["  csrr t1, mscratch"])
    lines.extend(check_block("t1", 0x1A, 4))
    lines.extend(
        [
            "",
            "csr_csrrwi:",
            "  li TESTNUM, 5",
            "  li t0, 0x123",
            "  csrw mscratch, t0",
            "  csrrwi t1, mscratch, 31",
        ]
    )
    lines.extend(check_block("t1", 0x123, 5))
    lines.extend(["  csrr t1, mscratch"])
    lines.extend(check_block("t1", 0x1F, 5))
    lines.extend(
        [
            "",
            "csr_csrrsi:",
            "  li TESTNUM, 6",
            "  li t0, 0x01",
            "  csrw mscratch, t0",
            "  csrrsi t1, mscratch, 16",
        ]
    )
    lines.extend(check_block("t1", 0x01, 6))
    lines.extend(["  csrr t1, mscratch"])
    lines.extend(check_block("t1", 0x11, 6))
    lines.extend(
        [
            "",
            "csr_csrrci:",
            "  li TESTNUM, 7",
            "  li t0, 0x1f",
            "  csrw mscratch, t0",
            "  csrrci t1, mscratch, 5",
        ]
    )
    lines.extend(check_block("t1", 0x1F, 7))
    lines.extend(["  csrr t1, mscratch"])
    lines.extend(check_block("t1", 0x1A, 7))
    lines.extend(
        [
            "",
            "csr_suppressed_writes:",
            "  li TESTNUM, 8",
            "  li t0, 0x55aa",
            "  csrw mscratch, t0",
            "  csrrs t1, mscratch, x0",
            "  csrrc t2, mscratch, x0",
            "  csrrsi t3, mscratch, 0",
            "  csrrci t5, mscratch, 0",
        ]
    )
    for register in ("t1", "t2", "t3", "t5"):
        lines.extend(check_block(register, 0x55AA, 8))
    lines.extend(
        [
            "",
            "csr_rd_zero_suppresses_read:",
            "  li TESTNUM, 9",
            "  li t0, 0x5a5a",
            "  csrrw x0, mscratch, t0",
            "  csrr t1, mscratch",
        ]
    )
    lines.extend(check_block("t1", 0x5A5A, 9))
    lines.extend(
        [
            "  csrrwi x0, mscratch, 31",
            "  csrr t1, mscratch",
        ]
    )
    lines.extend(check_block("t1", 0x1F, 9))
    lines.extend(
        [
            "",
            "csr_rd_rs1_alias:",
            "  li TESTNUM, 10",
            "  li t0, 0x33",
            "  csrw mscratch, t0",
            "  li t0, 0x77",
            "  csrrw t0, mscratch, t0",
        ]
    )
    lines.extend(check_block("t0", 0x33, 10))
    lines.extend(["  csrr t1, mscratch"])
    lines.extend(check_block("t1", 0x77, 10))
    lines.extend(
        [
            "",
            "csr_known_illegal_instruction:",
            "  li TESTNUM, 11",
            "  mv s2, s0",
            "  .word 0x00000000",
            "  addi s2, s2, 1",
            "  bne s0, s2, fail",
            "",
            "csr_read_only_write_trap:",
            "  li TESTNUM, 12",
            "  mv s2, s0",
            "  csrrw x0, mvendorid, x0",
            "  addi s2, s2, 1",
            "  bne s0, s2, fail",
            "",
            "  # Restore state changed by the safe semantic tests.",
            "  csrw mscratch, s3",
            "  li TESTNUM, 13",
            "  j pass",
            "",
            "  .align 2",
            "  .global mtvec_handler",
            "mtvec_handler:",
            "  csrr t0, mcause",
            "  li t1, CAUSE_ILLEGAL_INSTRUCTION",
            "  bne t0, t1, csr_unexpected_trap",
            "  csrr t0, mepc",
            "  addi t0, t0, 4",
            "  csrw mepc, t0",
            "  addi s0, s0, 1",
            "  mret",
            "",
            "csr_unexpected_trap:",
            "  li TESTNUM, 0x7ff",
            "  j fail",
            "",
            "  TEST_PASSFAIL",
            "",
            "RVTEST_CODE_END",
            "",
            "RVTEST_DATA_BEGIN",
            "  TEST_DATA",
            "RVTEST_DATA_END",
            "",
        ]
    )
    return "\n".join(lines)


def render_csr_map_assembly() -> str:
    lines = [
        '#include "riscv_test.h"',
        '#include "test_macros.h"',
        "",
        "  .option norelax",
        "RVTEST_RV64M",
        "RVTEST_CODE_BEGIN",
        "",
        "  .option norvc",
        "  .align 2",
        "  li TESTNUM, 2",
        "  li s0, 0",
        "  li s1, 0",
        "",
        "csr_all_address_read_map:",
        "  # Every CSR address is probed with all four architecturally",
        "  # non-writing read forms. Illegal accesses recover in the handler.",
    ]

    for csr in range(CSR_COUNT):
        lines.append(f"csr_address_{csr:03x}:")
        lines.append(f"  li s1, 0x{csr:03x}")
        for operation in SAFE_READ_OPERATIONS:
            lines.append(
                f"  .word 0x{encode_csr(csr, operation.funct3, 0, 0):08x}"
                f"  # {operation.name} x0, 0x{csr:03x}, 0"
            )

    lines.extend(
        [
            "",
            "  li TESTNUM, 3",
            "  j pass",
            "",
            "  .align 2",
            "  .global mtvec_handler",
            "mtvec_handler:",
            "  csrr t0, mcause",
            "  li t1, CAUSE_ILLEGAL_INSTRUCTION",
            "  bne t0, t1, csr_unexpected_trap",
            "  csrr t0, mepc",
            "  addi t0, t0, 4",
            "  csrw mepc, t0",
            "  addi s0, s0, 1",
            "  mret",
            "",
            "csr_unexpected_trap:",
            "  li TESTNUM, 0x7ff",
            "  j fail",
            "",
            "  TEST_PASSFAIL",
            "",
            "RVTEST_CODE_END",
            "",
            "RVTEST_DATA_BEGIN",
            "  TEST_DATA",
            "RVTEST_DATA_END",
            "",
        ]
    )
    return "\n".join(lines)

def render_msip_assembly() -> str:
    return """#include "riscv_test.h"
#include "test_macros.h"

  .option norelax
RVTEST_RV64M
RVTEST_CODE_BEGIN

  .option norvc
  .align 2

  # Whiteboard flow: enable mstatus.MIE and mie.MSIE, write CLINT MSIP,
  # check mcause in the machine trap handler, clear MSIP, and return.
  li TESTNUM, 2
  li s0, 0

  li t0, MIP_MSIP
  csrs mie, t0
  li t0, MSTATUS_MIE
  csrs mstatus, t0

  li t0, 0x02000000
  li t1, 1
  sw t1, 0(t0)

msip_wait:
  beqz s0, msip_wait

  # Disable the source and global enable before reporting PASS.
  li t0, MIP_MSIP
  csrc mie, t0
  li t0, MSTATUS_MIE
  csrc mstatus, t0
  li TESTNUM, 3
  j pass

  .align 2
  .global mtvec_handler
mtvec_handler:
  csrr t0, mcause
  li t1, 1
  slli t1, t1, 63
  ori t1, t1, IRQ_M_SOFT
  bne t0, t1, msip_unexpected_trap

  # MSIP is memory-mapped, not a CSR. Clear it before mret.
  li t0, 0x02000000
  sw zero, 0(t0)
  li s0, 1
  mret

msip_unexpected_trap:
  li TESTNUM, 0x7fe
  j fail

  TEST_PASSFAIL

RVTEST_CODE_END

RVTEST_DATA_BEGIN
  TEST_DATA
RVTEST_DATA_END
"""


def write_ascii(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="ascii", newline="\n")


def print_summary(stream: TextIO) -> None:
    print("CSR address count:             4,096", file=stream)
    print(f"Register-form encodings:      {REGISTER_FORM_COUNT:,}", file=stream)
    print(f"Immediate-form encodings:     {IMMEDIATE_FORM_COUNT:,}", file=stream)
    print(f"All six instruction encodings:{ENCODING_COUNT:>15,}", file=stream)
    print("Generated safe map probes:    16,384", file=stream)
    print("Execution mode:               RV64 machine mode", file=stream)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate exhaustive-safe CSR verification assembly."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("csr_random.S"),
        help="CSR assembly output (default: csr_random.S)",
    )
    parser.add_argument(
        "--interrupt-output",
        type=Path,
        default=Path("csr_msip.S"),
        help="MSIP assembly output (default: csr_msip.S)",
    )
    parser.add_argument(
        "--map-output",
        type=Path,
        default=Path("csr_map.S"),
        help="full 4,096-address diagnostic map (default: csr_map.S)",
    )
    parser.add_argument(
        "--encoding-manifest",
        type=Path,
        help="optional gzip CSV with all 25,165,824 instruction-field encodings",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    write_ascii(arguments.output, render_csr_assembly())
    write_ascii(arguments.map_output, render_csr_map_assembly())
    write_ascii(arguments.interrupt_output, render_msip_assembly())
    print_summary(stream=__import__("sys").stdout)
    print(f"Generated CSR test:  {arguments.output}")
    print(f"Generated CSR map:   {arguments.map_output}")
    print(f"Generated MSIP test: {arguments.interrupt_output}")

    if arguments.encoding_manifest is not None:
        print("Writing the complete compressed encoding manifest...")
        write_encoding_manifest(arguments.encoding_manifest)
        print(f"Generated manifest:  {arguments.encoding_manifest}")
    else:
        print("Full manifest skipped; use --encoding-manifest FILE.csv.gz if required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
