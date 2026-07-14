#include "riscv_test.h"
#include "test_macros.h"

#define FFLAG_NV 0x10

.macro CHECK_FMAX testnum, fd, fs1, fs2, val1, val2, expected, flags
test_\testnum:
  li TESTNUM, \testnum
  fsflags x0
  li x10, \val1
  fmv.w.x \fs1, x10
  li x11, \val2
  fmv.w.x \fs2, x11
  fmax.s \fd, \fs1, \fs2
  fmv.x.w x12, \fd
  li x13, \expected
  sext.w x13, x13
  bne x12, x13, fail
  frflags x14
  li x15, \flags
  bne x14, x15, fail
.endm

RVTEST_RV64UF
RVTEST_CODE_BEGIN

fmax_s_ordered_positive:
  CHECK_FMAX 2, f0, f1, f2, 0x3f800000, 0x40000000, 0x40000000, 0
fmax_s_ordered_positive_reversed:
  CHECK_FMAX 3, f3, f4, f5, 0x40000000, 0x3f800000, 0x40000000, 0
fmax_s_ordered_negative:
  CHECK_FMAX 4, f6, f7, f8, 0xbf800000, 0xc0000000, 0xbf800000, 0
fmax_s_signed_zero:
  CHECK_FMAX 5, f9, f10, f11, 0x80000000, 0x00000000, 0x00000000, 0
fmax_s_signed_zero_reversed:
  CHECK_FMAX 6, f12, f13, f14, 0x00000000, 0x80000000, 0x00000000, 0
fmax_s_positive_infinity:
  CHECK_FMAX 7, f15, f16, f17, 0x7f800000, 0x7f7fffff, 0x7f800000, 0
fmax_s_negative_infinity:
  CHECK_FMAX 8, f18, f19, f20, 0xff800000, 0xbf800000, 0xbf800000, 0
fmax_s_subnormal:
  CHECK_FMAX 9, f21, f22, f23, 0x00000001, 0x00000002, 0x00000002, 0
fmax_s_negative_subnormal:
  CHECK_FMAX 10, f24, f25, f26, 0x80000001, 0x80000002, 0x80000001, 0

fmax_s_qnan_left:
  CHECK_FMAX 11, f27, f28, f29, 0x7fc12345, 0x3fc00000, 0x3fc00000, 0
fmax_s_qnan_right:
  CHECK_FMAX 12, f30, f31, f0, 0x3fc00000, 0x7fc12345, 0x3fc00000, 0
fmax_s_two_qnans:
  # Avoid f1 because some C-Class dump loggers emit f1 and fflags fields in
  # a different textual order from Spike. The checked operation is unchanged.
  CHECK_FMAX 13, f4, f2, f3, 0x7fc12345, 0x7fffffff, 0x7fc00000, 0
fmax_s_snan_left:
  CHECK_FMAX 14, f4, f5, f6, 0x7f800001, 0x3fc00000, 0x3fc00000, FFLAG_NV
fmax_s_snan_right:
  CHECK_FMAX 15, f7, f8, f9, 0x3fc00000, 0x7f800001, 0x3fc00000, FFLAG_NV
fmax_s_two_snans:
  CHECK_FMAX 16, f10, f11, f12, 0x7f800001, 0xff800001, 0x7fc00000, FFLAG_NV

fmax_s_rd_equals_rs1:
  CHECK_FMAX 17, f13, f13, f14, 0x40400000, 0x40000000, 0x40400000, 0
fmax_s_rd_equals_rs2:
  CHECK_FMAX 18, f15, f16, f15, 0x40000000, 0x40400000, 0x40400000, 0

fmax_s_raw_no_gap:
  li TESTNUM, 19
  fsflags x0
  li x10, 0x3f000000
  fmv.w.x f17, x10
  li x11, 0x3f800000
  fmv.w.x f18, x11
  fmax.s f19, f17, f18
  fmv.x.w x12, f19
  li x13, 0x3f800000
  bne x12, x13, fail
  frflags x14
  bnez x14, fail

fmax_s_raw_one_gap:
  li TESTNUM, 20
  fsflags x0
  li x10, 0x40000000
  fmv.w.x f20, x10
  li x11, 0x40400000
  fmv.w.x f21, x11
  nop
  fmax.s f22, f20, f21
  fmv.x.w x12, f22
  li x13, 0x40400000
  bne x12, x13, fail

fmax_s_chained_dependency:
  li TESTNUM, 21
  fsflags x0
  li x10, 0x3f800000
  fmv.w.x f23, x10
  li x11, 0x40000000
  fmv.w.x f24, x11
  li x12, 0x40400000
  fmv.w.x f25, x12
  fmax.s f26, f23, f24
  fmax.s f27, f26, f25
  fmv.x.w x13, f27
  li x14, 0x40400000
  bne x13, x14, fail

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN
  TEST_DATA
RVTEST_DATA_END
