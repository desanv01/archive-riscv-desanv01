#include "riscv_test.h"
#include "test_macros.h"

.macro CHECK_AMOOR testnum, insn, oldval, operand, oldresult, newresult
test_\testnum:
  li TESTNUM, \testnum
  la x10, amoor_scratch
  li x11, \oldval
  sw x11, 0(x10)
  li x12, \operand
  \insn x13, x12, (x10)
  li x14, \oldresult
  bne x13, x14, fail
  lwu x15, 0(x10)
  li x16, \newresult
  bne x15, x16, fail
.endm

RVTEST_RV64U
RVTEST_CODE_BEGIN

amoor_w_zero_zero:
  CHECK_AMOOR 2, amoor.w, 0x00000000, 0x00000000, 0x0000000000000000, 0x00000000
amoor_w_zero_ones:
  CHECK_AMOOR 3, amoor.w, 0x00000000, 0xffffffff, 0x0000000000000000, 0xffffffff
amoor_w_ones_zero_signextend:
  CHECK_AMOOR 4, amoor.w, 0xffffffff, 0x00000000, 0xffffffffffffffff, 0xffffffff
amoor_w_alternating:
  CHECK_AMOOR 5, amoor.w, 0xaaaaaaaa, 0x55555555, 0xffffffffaaaaaaaa, 0xffffffff
amoor_w_sparse_union:
  CHECK_AMOOR 6, amoor.w, 0x80000001, 0x00010010, 0xffffffff80000001, 0x80010011
amoor_w_upper_rs2_ignored:
  CHECK_AMOOR 7, amoor.w, 0x00000000, 0xdeadbeef00000001, 0x0000000000000000, 0x00000001

amoor_w_aq:
  CHECK_AMOOR 8, amoor.w.aq, 0x01010101, 0x10101010, 0x0000000001010101, 0x11111111
amoor_w_rl:
  CHECK_AMOOR 9, amoor.w.rl, 0x0f0f0f0f, 0xf0000000, 0x000000000f0f0f0f, 0xff0f0f0f
amoor_w_aqrl:
  CHECK_AMOOR 10, amoor.w.aqrl, 0x12340000, 0x00005678, 0x0000000012340000, 0x12345678

amoor_w_rd_equals_rs2:
  li TESTNUM, 11
  la x10, amoor_scratch
  li x11, 0x0000f000
  sw x11, 0(x10)
  li x12, 0x000000ff
  amoor.w x12, x12, (x10)
  li x14, 0x000000000000f000
  bne x12, x14, fail
  lwu x15, 0(x10)
  li x16, 0x0000f0ff
  bne x15, x16, fail

amoor_w_rd_equals_rs1:
  li TESTNUM, 12
  la x10, amoor_scratch
  mv x17, x10
  li x11, 0x80000000
  sw x11, 0(x10)
  li x12, 0x00000001
  amoor.w x10, x12, (x10)
  li x14, 0xffffffff80000000
  bne x10, x14, fail
  lwu x15, 0(x17)
  li x16, 0x80000001
  bne x15, x16, fail

amoor_w_rs2_zero:
  li TESTNUM, 13
  la x10, amoor_scratch
  li x11, 0x89abcdef
  sw x11, 0(x10)
  amoor.w x13, x0, (x10)
  li x14, 0xffffffff89abcdef
  bne x13, x14, fail
  lwu x15, 0(x10)
  li x16, 0x89abcdef
  bne x15, x16, fail

amoor_w_rd_zero:
  li TESTNUM, 14
  la x10, amoor_scratch
  li x11, 0x000000f0
  sw x11, 0(x10)
  li x12, 0x00000f00
  amoor.w x0, x12, (x10)
  lwu x15, 0(x10)
  li x16, 0x00000ff0
  bne x15, x16, fail

amoor_w_address_raw_no_gap:
  li TESTNUM, 15
  li x12, 0x0000000f
  la x10, amoor_scratch
  amoor.w x13, x12, (x10)
  lwu x15, 0(x10)
  ori x16, x13, 0x0f
  sext.w x13, x13
  bne x15, x16, fail

amoor_w_source_raw_no_gap:
  li TESTNUM, 16
  la x10, amoor_scratch
  li x11, 0x00ff0000
  sw x11, 0(x10)
  li x12, 0x0000ff00
  amoor.w x13, x12, (x10)
  addi x14, x13, 1
  li x16, 0x00ff0001
  bne x14, x16, fail
  lwu x15, 0(x10)
  li x16, 0x00ffff00
  bne x15, x16, fail

amoor_w_back_to_back:
  li TESTNUM, 17
  la x10, amoor_scratch
  sw x0, 0(x10)
  li x11, 0x0000000f
  li x12, 0x000000f0
  amoor.w x18, x11, (x10)
  amoor.w x19, x12, (x10)
  bnez x18, fail
  li x14, 0x0000000f
  bne x19, x14, fail
  lwu x15, 0(x10)
  li x16, 0x000000ff
  bne x15, x16, fail

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN
  .align 3
amoor_scratch:
  .dword 0
RVTEST_DATA_END
