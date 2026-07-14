#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64U
RVTEST_CODE_BEGIN


store_test:

    # Load addresses of data
    la x4, _data1
    la x5, _data2
    la x6, _data3
    
    # Load word from memory address
    lw a0, 0(x4)
    lw a1, 0(x5)
    lw a2, 0(x6)

    # Load memory addresses to store data
    li s0, 0x80003000

    # Store word to memory addresses
    sw a0, 0(s0)   
    sw a1, 4(s0)
    sw a2, 8(s0)

  RVTEST_PASS
RVTEST_CODE_END

    .data
    _data1:
    .word 0xbaadf00d
    _data2:
    .word 0xcafed00d
    _data3:
    .word 0xdeadbeef


RVTEST_DATA_BEGIN
    .align 3

result:
    .dword -1

RVTEST_DATA_END
