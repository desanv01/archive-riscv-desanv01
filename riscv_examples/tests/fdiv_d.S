#include "riscv_test.h"
#include "test_macros.h"

#define FFLAG_NX 0x01
#define FFLAG_UF_NX 0x03
#define FFLAG_OF_NX 0x05
#define FFLAG_DZ 0x08
#define FFLAG_NV 0x10

.macro CHECK_FDIV testnum, fd, fs1, fs2, val1, val2, expected, flags, rm
test_\testnum:
  li TESTNUM, \testnum
  fsflags x0
  li x10, \val1
  fmv.d.x \fs1, x10
  li x11, \val2
  fmv.d.x \fs2, x11
  fdiv.d \fd, \fs1, \fs2, \rm
  fmv.x.d x12, \fd
  li x13, \expected
  bne x12, x13, fail
  frflags x14
  li x15, \flags
  bne x14, x15, fail
.endm

.macro CHECK_FDIV_DYN testnum, fd, fs1, fs2, val1, val2, expected, flags, mode
test_\testnum:
  li TESTNUM, \testnum
  li x16, \mode
  fsrm x0, x16
  fsflags x0
  li x10, \val1
  fmv.d.x \fs1, x10
  li x11, \val2
  fmv.d.x \fs2, x11
  fdiv.d \fd, \fs1, \fs2, dyn
  fmv.x.d x12, \fd
  li x13, \expected
  bne x12, x13, fail
  frflags x14
  li x15, \flags
  bne x14, x15, fail
  fsrm x0, x0
.endm

RVTEST_RV64UF
RVTEST_CODE_BEGIN

fdiv_d_exact_positive:
  CHECK_FDIV 2, f0, f1, f2, 0x4018000000000000, 0x4008000000000000, 0x4000000000000000, 0, rne
fdiv_d_exact_negative:
  CHECK_FDIV 3, f3, f4, f5, 0xc018000000000000, 0x4008000000000000, 0xc000000000000000, 0, rne
fdiv_d_positive_zero:
  CHECK_FDIV 4, f6, f7, f8, 0x0000000000000000, 0x4000000000000000, 0x0000000000000000, 0, rne
fdiv_d_negative_zero:
  CHECK_FDIV 5, f9, f10, f11, 0x8000000000000000, 0x4000000000000000, 0x8000000000000000, 0, rne
fdiv_d_divide_by_zero:
  CHECK_FDIV 6, f12, f13, f14, 0x3ff0000000000000, 0x0000000000000000, 0x7ff0000000000000, FFLAG_DZ, rne
fdiv_d_negative_divide_by_zero:
  CHECK_FDIV 7, f15, f16, f17, 0xbff0000000000000, 0x0000000000000000, 0xfff0000000000000, FFLAG_DZ, rne
fdiv_d_zero_by_zero:
  CHECK_FDIV 8, f18, f19, f20, 0x0000000000000000, 0x0000000000000000, 0x7ff8000000000000, FFLAG_NV, rne
fdiv_d_inf_by_inf:
  CHECK_FDIV 9, f21, f22, f23, 0x7ff0000000000000, 0x7ff0000000000000, 0x7ff8000000000000, FFLAG_NV, rne
fdiv_d_inf_by_finite:
  CHECK_FDIV 10, f24, f25, f26, 0x7ff0000000000000, 0x4000000000000000, 0x7ff0000000000000, 0, rne
fdiv_d_finite_by_inf:
  CHECK_FDIV 11, f27, f28, f29, 0x4000000000000000, 0x7ff0000000000000, 0x0000000000000000, 0, rne
fdiv_d_qnan:
  CHECK_FDIV 12, f30, f31, f0, 0x7ff8123456789abc, 0x3ff0000000000000, 0x7ff8000000000000, 0, rne
fdiv_d_snan:
  # Avoid f1 here because the legacy RTL logger emits f1 and fflags in a
  # different textual order from Spike. The checked values are unchanged.
  CHECK_FDIV 13, f4, f2, f3, 0x7ff0000000000001, 0x3ff0000000000000, 0x7ff8000000000000, FFLAG_NV, rne

fdiv_d_one_third_rne:
  CHECK_FDIV 14, f4, f5, f6, 0x3ff0000000000000, 0x4008000000000000, 0x3fd5555555555555, FFLAG_NX, rne
fdiv_d_one_third_rtz:
  CHECK_FDIV 15, f7, f8, f9, 0x3ff0000000000000, 0x4008000000000000, 0x3fd5555555555555, FFLAG_NX, rtz
fdiv_d_one_third_rdn:
  CHECK_FDIV 16, f10, f11, f12, 0x3ff0000000000000, 0x4008000000000000, 0x3fd5555555555555, FFLAG_NX, rdn
fdiv_d_one_third_rup:
  CHECK_FDIV 17, f13, f14, f15, 0x3ff0000000000000, 0x4008000000000000, 0x3fd5555555555556, FFLAG_NX, rup
fdiv_d_one_third_rmm:
  CHECK_FDIV 18, f16, f17, f18, 0x3ff0000000000000, 0x4008000000000000, 0x3fd5555555555555, FFLAG_NX, rmm
fdiv_d_negative_third_rdn:
  CHECK_FDIV 19, f19, f20, f21, 0xbff0000000000000, 0x4008000000000000, 0xbfd5555555555556, FFLAG_NX, rdn
fdiv_d_dynamic_rup:
  CHECK_FDIV_DYN 20, f22, f23, f24, 0x3ff0000000000000, 0x4008000000000000, 0x3fd5555555555556, FFLAG_NX, 3

fdiv_d_exact_subnormal:
  CHECK_FDIV 21, f25, f26, f27, 0x0010000000000000, 0x4000000000000000, 0x0008000000000000, 0, rne
fdiv_d_underflow:
  CHECK_FDIV 22, f28, f29, f30, 0x0000000000000001, 0x4000000000000000, 0x0000000000000000, FFLAG_UF_NX, rne
fdiv_d_overflow_rne:
  CHECK_FDIV 23, f31, f0, f1, 0x7fefffffffffffff, 0x3fe0000000000000, 0x7ff0000000000000, FFLAG_OF_NX, rne
fdiv_d_overflow_rtz:
  CHECK_FDIV 24, f2, f3, f4, 0x7fefffffffffffff, 0x3fe0000000000000, 0x7fefffffffffffff, FFLAG_OF_NX, rtz

fdiv_d_rd_equals_rs1:
  CHECK_FDIV 25, f5, f5, f6, 0x4010000000000000, 0x4000000000000000, 0x4000000000000000, 0, rne
fdiv_d_rd_equals_rs2:
  CHECK_FDIV 26, f7, f8, f7, 0x4010000000000000, 0x4000000000000000, 0x4000000000000000, 0, rne

fdiv_d_chained_dependency:
  li TESTNUM, 27
  fsrm x0, x0
  fsflags x0
  li x10, 0x4020000000000000
  fmv.d.x f9, x10
  li x11, 0x4000000000000000
  fmv.d.x f10, x11
  fdiv.d f11, f9, f10, rne
  fdiv.d f12, f11, f10, rne
  fmv.x.d x12, f12
  li x13, 0x4000000000000000
  bne x12, x13, fail
  frflags x14
  bnez x14, fail

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN
  TEST_DATA
RVTEST_DATA_END
