#!/usr/bin/env python3
"""Generate register-field combinations for the RISC-V MUL instruction."""

from __future__ import annotations

import argparse
import sys
from itertools import combinations, permutations, product
from math import comb, perm
from pathlib import Path
from typing import Iterable, Iterator

RegisterTriple = tuple[int, int, int]
REGISTER_COUNT = 32


def generate_cases(mode: str) -> Iterator[RegisterTriple]:
    """Yield (rd, rs1, rs2) register-number triples for the selected mode."""
    registers = range(REGISTER_COUNT)

    if mode == "combinations":
        yield from combinations(registers, 3)
    elif mode == "distinct-ordered":
        yield from permutations(registers, 3)
    elif mode == "all-ordered":
        yield from product(registers, repeat=3)
    else:
        raise ValueError(f"Unsupported generation mode: {mode}")


def expected_count(mode: str) -> int:
    if mode == "combinations":
        return comb(REGISTER_COUNT, 3)
    if mode == "distinct-ordered":
        return perm(REGISTER_COUNT, 3)
    if mode == "all-ordered":
        return REGISTER_COUNT**3
    raise ValueError(f"Unsupported generation mode: {mode}")


def validate_cases(cases: Iterable[RegisterTriple], mode: str) -> list[RegisterTriple]:
    """Materialize and validate generated cases before producing output."""
    materialized = list(cases)
    expected = expected_count(mode)

    if len(materialized) != expected:
        raise RuntimeError(f"Generated {len(materialized)} cases; expected {expected}")
    if len(set(materialized)) != expected:
        raise RuntimeError("Generated register triples are not unique")

    for rd, rs1, rs2 in materialized:
        if not all(0 <= register < REGISTER_COUNT for register in (rd, rs1, rs2)):
            raise RuntimeError(f"Out-of-range register in {(rd, rs1, rs2)}")
        if mode in {"combinations", "distinct-ordered"} and len({rd, rs1, rs2}) != 3:
            raise RuntimeError(f"Repeated register in distinct case {(rd, rs1, rs2)}")
        if mode == "combinations" and not rd < rs1 < rs2:
            raise RuntimeError(f"Combination is not in canonical order: {(rd, rs1, rs2)}")

    return materialized


def format_instruction(case: RegisterTriple) -> str:
    rd, rs1, rs2 = case
    return f"mul x{rd}, x{rs1}, x{rs2}"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate MUL rd, rs1, rs2 register combinations."
    )
    parser.add_argument(
        "--mode",
        choices=("combinations", "distinct-ordered", "all-ordered"),
        default="combinations",
        help=(
            "combinations: 32C3=4960 sorted triples; "
            "distinct-ordered: 32P3=29760 assignments; "
            "all-ordered: 32^3=32768 assignments including repeated registers"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("mul_register_combinations.txt"),
        help="output text file (default: mul_register_combinations.txt)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="write the file without printing every instruction to the terminal",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    cases = validate_cases(generate_cases(arguments.mode), arguments.mode)
    lines = [format_instruction(case) for case in cases]

    arguments.output.write_text("\n".join(lines) + "\n", encoding="ascii")

    if not arguments.quiet:
        for line in lines:
            print(line)

    print(
        f"Generated {len(lines)} unique MUL cases in {arguments.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
