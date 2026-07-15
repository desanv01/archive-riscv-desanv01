#include "riscv_test.h"
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
