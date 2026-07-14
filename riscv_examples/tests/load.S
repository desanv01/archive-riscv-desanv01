#include "riscv_test.h"
#include "test_macros.h"

RVTEST_RV64U
RVTEST_CODE_BEGIN


load_test:

    # Load addresses of data
    la x4, _data1
    la x5, _data2
    la x6, _data3

    # Load half-word from memory address
    lh s2, 0(x4)
    lh s3, 0(x5)
    lh s4, 0(x6)
    
    # Load word from memory address
    lw a0, 0(x4)
    lw a1, 0(x5)
    lw a2, 0(x6)

    #load double word from memory address
    ld a3, 0(x4)  

  RVTEST_PASS
RVTEST_CODE_END

    .data
    _data1:
    .dword 0xbaadf00d12345678
    _data2:
    .word 0xcafed00d
    _data3:
    .word 0xdeadbeef
RVTEST_DATA_BEGIN
    .align 3

result:
    .dword -1

RVTEST_DATA_END
