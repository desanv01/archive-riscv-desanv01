#include "riscv_test.h"
#include "test_macros.h"

.macro CHECK_CSLLI testnum, reg, input, shamt, expected
test_\testnum:
  li TESTNUM, \testnum
  li \reg, \input
  c.slli \reg, \shamt
  li x7, \expected
  bne \reg, x7, fail
.endm

RVTEST_RV64U
RVTEST_CODE_BEGIN

c_slli_zero:
  CHECK_CSLLI 2, x5, 0x0000000000000000, 1, 0x0000000000000000
c_slli_one_by_one:
  CHECK_CSLLI 3, x6, 0x0000000000000001, 1, 0x0000000000000002
c_slli_shift_31:
  CHECK_CSLLI 4, x8, 0x0000000000000001, 31, 0x0000000080000000
c_slli_shift_32:
  CHECK_CSLLI 5, x9, 0x0000000000000001, 32, 0x0000000100000000
c_slli_shift_63:
  CHECK_CSLLI 6, x10, 0x0000000000000001, 63, 0x8000000000000000
c_slli_all_ones_by_one:
  CHECK_CSLLI 7, x11, 0xffffffffffffffff, 1, 0xfffffffffffffffe
c_slli_all_ones_by_63:
  CHECK_CSLLI 8, x12, 0xffffffffffffffff, 63, 0x8000000000000000
c_slli_msb_discard:
  CHECK_CSLLI 9, x13, 0x8000000000000000, 1, 0x0000000000000000
c_slli_pattern_by_four:
  CHECK_CSLLI 10, x14, 0x0123456789abcdef, 4, 0x123456789abcdef0
c_slli_pattern_by_seventeen:
  CHECK_CSLLI 11, x15, 0x0000123456789abc, 17, 0x2468acf135780000
c_slli_register_x31:
  CHECK_CSLLI 12, x31, 0x0000000000000003, 5, 0x0000000000000060
c_slli_register_x1:
  CHECK_CSLLI 13, x1, 0x0000000000000007, 3, 0x0000000000000038

c_slli_result_raw_no_gap:
  li TESTNUM, 14
  li x16, 3
  c.slli x16, 4
  addi x17, x16, 1
  li x7, 49
  bne x17, x7, fail

c_slli_back_to_back:
  li TESTNUM, 15
  li x18, 1
  c.slli x18, 7
  c.slli x18, 8
  li x7, 0x0000000000008000
  bne x18, x7, fail

c_slli_one_cycle_gap:
  li TESTNUM, 16
  li x19, 0x11
  nop
  c.slli x19, 2
  nop
  addi x20, x19, 0
  li x7, 0x44
  bne x20, x7, fail

c_slli_hint_zero_shamt:
  li TESTNUM, 17
  li x5, 0x12345678
  .2byte 0x0282
  li x7, 0x12345678
  bne x5, x7, fail

c_slli_hint_rd_x0:
  li TESTNUM, 18
  .2byte 0x0006
  bnez x0, fail

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN
  TEST_DATA
RVTEST_DATA_END
