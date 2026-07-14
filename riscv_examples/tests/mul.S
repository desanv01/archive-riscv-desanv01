#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64U
RVTEST_CODE_BEGIN

  # Test numbers are kept in x3/gp by the harness. x3 and x4 are not operands.

mul_zero_zero:
  TEST_RR_OP( 2, mul, 0x0000000000000000, 0x0000000000000000, 0x0000000000000000 );
mul_zero_max:
  TEST_RR_OP( 3, mul, 0x0000000000000000, 0x0000000000000000, 0xffffffffffffffff );
mul_one_max:
  TEST_RR_OP( 4, mul, 0xffffffffffffffff, 0x0000000000000001, 0xffffffffffffffff );
mul_neg1_neg1:
  TEST_RR_OP( 5, mul, 0x0000000000000001, 0xffffffffffffffff, 0xffffffffffffffff );
mul_max_times_two:
  TEST_RR_OP( 6, mul, 0xfffffffffffffffe, 0x7fffffffffffffff, 0x0000000000000002 );
mul_min_times_neg1_wrap:
  TEST_RR_OP( 7, mul, 0x8000000000000000, 0x8000000000000000, 0xffffffffffffffff );
mul_min_times_two_wrap:
  TEST_RR_OP( 8, mul, 0x0000000000000000, 0x8000000000000000, 0x0000000000000002 );
mul_32bit_max_square:
  TEST_RR_OP( 9, mul, 0xfffffffe00000001, 0x00000000ffffffff, 0x00000000ffffffff );
mul_pattern_product:
  TEST_RR_OP( 10, mul, 0x2236d88fe5618cf0, 0x123456789abcdef0, 0x0fedcba987654321 );
mul_alternating_bits:
  TEST_RR_OP( 11, mul, 0x1c71c71c71c71c72, 0xaaaaaaaaaaaaaaaa, 0x5555555555555555 );
mul_high_low_mix:
  TEST_RR_OP( 12, mul, 0x8000000000000003, 0x8000000000000001, 0x0000000000000003 );
mul_max_square_low_half:
  TEST_RR_OP( 13, mul, 0x0000000000000001, 0x7fffffffffffffff, 0x7fffffffffffffff );

mul_rd_equals_rs1:
  TEST_RR_SRC1_EQ_DEST( 14, mul, 0x0000000000000075, 0x0000000000000009, 0x000000000000000d );
mul_rd_equals_rs2:
  TEST_RR_SRC2_EQ_DEST( 15, mul, 0x000000000000009a, 0x000000000000000e, 0x000000000000000b );
mul_all_operands_same:
  TEST_RR_SRC12_EQ_DEST( 16, mul, 0x00000000000000a9, 0x000000000000000d );
mul_rs1_zero:
  TEST_RR_ZEROSRC1( 17, mul, 0x0000000000000000, 0xdeadbeefcafef00d );
mul_rs2_zero:
  TEST_RR_ZEROSRC2( 18, mul, 0x0000000000000000, 0xdeadbeefcafef00d );
mul_both_sources_zero:
  TEST_RR_ZEROSRC12( 19, mul, 0x0000000000000000 );
mul_zero_destination:
  TEST_RR_ZERODEST( 20, mul, 0x123456789abcdef0, 0x0fedcba987654321 );

mul_raw_sources_no_gap:
  li TESTNUM, 21
  li x10, 7
  li x11, 9
  mul x12, x10, x11
  li x7, 63
  bne x12, x7, fail

mul_raw_result_no_gap:
  li TESTNUM, 22
  li x13, 12
  li x14, 13
  mul x15, x13, x14
  addi x16, x15, 1
  li x7, 157
  bne x16, x7, fail

mul_source_one_cycle_gap:
  li TESTNUM, 23
  li x17, 17
  nop
  li x18, 19
  nop
  mul x19, x17, x18
  li x7, 323
  bne x19, x7, fail

mul_chained_dependency:
  li TESTNUM, 24
  li x20, 3
  li x21, 5
  mul x22, x20, x21
  mul x23, x22, x21
  li x7, 75
  bne x23, x7, fail

mul_waw_same_destination:
  li TESTNUM, 25
  li x24, 6
  li x25, 7
  mul x26, x24, x25
  li x27, 8
  mul x26, x26, x27
  li x7, 336
  bne x26, x7, fail

mul_register_bank_edges:
  li TESTNUM, 26
  li x1, 11
  li x31, 12
  mul x30, x1, x31
  li x7, 132
  bne x30, x7, fail

  TEST_PASSFAIL

RVTEST_CODE_END

  .data
RVTEST_DATA_BEGIN
  TEST_DATA
RVTEST_DATA_END
