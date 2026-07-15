#include "riscv_test.h"
#include "test_macros.h"

  .option norelax
RVTEST_RV64M
RVTEST_CODE_BEGIN

  .option norvc
  .align 2

  # s0 counts recovered illegal-instruction traps.
  # s1 identifies the current CSR address during the full map.
  li s0, 0
  li s1, 0

  # Preserve mscratch, the safe writable CSR used by semantic tests.
  csrr s3, mscratch

csr_csrrw:
  li TESTNUM, 2
  csrw mscratch, zero
  li t0, 0x0123456789abcdef
  csrrw t1, mscratch, t0
  bnez t1, fail
  csrr t2, mscratch
  li TESTNUM, 2
  li t4, 0x0123456789abcdef
  bne t2, t4, fail

csr_csrrs:
  li TESTNUM, 3
  li t0, 0x10
  csrw mscratch, t0
  li t2, 0x05
  csrrs t1, mscratch, t2
  li TESTNUM, 3
  li t4, 0x0000000000000010
  bne t1, t4, fail
  csrr t1, mscratch
  li TESTNUM, 3
  li t4, 0x0000000000000015
  bne t1, t4, fail

csr_csrrc:
  li TESTNUM, 4
  li t0, 0x1f
  csrw mscratch, t0
  li t2, 0x05
  csrrc t1, mscratch, t2
  li TESTNUM, 4
  li t4, 0x000000000000001f
  bne t1, t4, fail
  csrr t1, mscratch
  li TESTNUM, 4
  li t4, 0x000000000000001a
  bne t1, t4, fail

csr_csrrwi:
  li TESTNUM, 5
  li t0, 0x123
  csrw mscratch, t0
  csrrwi t1, mscratch, 31
  li TESTNUM, 5
  li t4, 0x0000000000000123
  bne t1, t4, fail
  csrr t1, mscratch
  li TESTNUM, 5
  li t4, 0x000000000000001f
  bne t1, t4, fail

csr_csrrsi:
  li TESTNUM, 6
  li t0, 0x01
  csrw mscratch, t0
  csrrsi t1, mscratch, 16
  li TESTNUM, 6
  li t4, 0x0000000000000001
  bne t1, t4, fail
  csrr t1, mscratch
  li TESTNUM, 6
  li t4, 0x0000000000000011
  bne t1, t4, fail

csr_csrrci:
  li TESTNUM, 7
  li t0, 0x1f
  csrw mscratch, t0
  csrrci t1, mscratch, 5
  li TESTNUM, 7
  li t4, 0x000000000000001f
  bne t1, t4, fail
  csrr t1, mscratch
  li TESTNUM, 7
  li t4, 0x000000000000001a
  bne t1, t4, fail

csr_suppressed_writes:
  li TESTNUM, 8
  li t0, 0x55aa
  csrw mscratch, t0
  csrrs t1, mscratch, x0
  csrrc t2, mscratch, x0
  csrrsi t3, mscratch, 0
  csrrci t5, mscratch, 0
  li TESTNUM, 8
  li t4, 0x00000000000055aa
  bne t1, t4, fail
  li TESTNUM, 8
  li t4, 0x00000000000055aa
  bne t2, t4, fail
  li TESTNUM, 8
  li t4, 0x00000000000055aa
  bne t3, t4, fail
  li TESTNUM, 8
  li t4, 0x00000000000055aa
  bne t5, t4, fail

csr_rd_zero_suppresses_read:
  li TESTNUM, 9
  li t0, 0x5a5a
  csrrw x0, mscratch, t0
  csrr t1, mscratch
  li TESTNUM, 9
  li t4, 0x0000000000005a5a
  bne t1, t4, fail
  csrrwi x0, mscratch, 31
  csrr t1, mscratch
  li TESTNUM, 9
  li t4, 0x000000000000001f
  bne t1, t4, fail

csr_rd_rs1_alias:
  li TESTNUM, 10
  li t0, 0x33
  csrw mscratch, t0
  li t0, 0x77
  csrrw t0, mscratch, t0
  li TESTNUM, 10
  li t4, 0x0000000000000033
  bne t0, t4, fail
  csrr t1, mscratch
  li TESTNUM, 10
  li t4, 0x0000000000000077
  bne t1, t4, fail

csr_known_illegal_instruction:
  li TESTNUM, 11
  mv s2, s0
  .word 0x00000000
  addi s2, s2, 1
  bne s0, s2, fail

csr_read_only_write_trap:
  li TESTNUM, 12
  mv s2, s0
  csrrw x0, mvendorid, x0
  addi s2, s2, 1
  bne s0, s2, fail

  # Restore state changed by the safe semantic tests.
  csrw mscratch, s3
  li TESTNUM, 13
  j pass

  .align 2
  .global mtvec_handler
mtvec_handler:
  csrr t0, mcause
  li t1, CAUSE_ILLEGAL_INSTRUCTION
  bne t0, t1, csr_unexpected_trap
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  addi s0, s0, 1
  mret

csr_unexpected_trap:
  li TESTNUM, 0x7ff
  j fail

  TEST_PASSFAIL

RVTEST_CODE_END

RVTEST_DATA_BEGIN
  TEST_DATA
RVTEST_DATA_END
