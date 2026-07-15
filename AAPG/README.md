# AAPG RV64IMAFDC Verification Suite

This directory contains 32 complete AAPG YAML configurations, deterministic
generation metadata, a Spike/C-Class runner, UCIS functional coverage, and an
interactive instruction-frequency histogram.

The supported comparison ISA is:

```text
rv64imafdczicsr_zifencei
```

The suite intentionally does not enable Vector or Zb instructions because they
are not enabled in the supplied C-Class verification Makefile.

## Files

```text
AAPG/
|-- configs/                 32 complete standalone AAPG YAML files
|-- tests/                   Python structural/unit tests
|-- generate_configs.py      Reproducibly regenerates all YAML files
|-- suite_manifest.yaml      Seeds, program counts, categories, expectations
|-- run_suite.py             Generate/build/Spike/C-Class orchestration
|-- cov.py                   Log parser, UCIS XML, CSV/JSON, HTML histogram
|-- Makefile                 Short user-facing commands
`-- requirements.txt         AAPG and PyYAML versions
```

Generated files appear under:

```text
work/suites/<suite-id>/work/  Isolated standard AAPG runtime (asm/common/bin/objdump/log)
work/log/*.log                Dynamic Spike execution logs used by cov.py
work/log/*.dump               Spike commit dumps
work/log/*.rtl.dump           C-Class commit dumps
work/log/*.diff               Mismatch details, only when a comparison fails
work/objdump/*.objdump        Static disassembly for every generated program
cov.xml                       Functional Coverage Viewer input
coverage/instruction_counts.csv
coverage/coverage_summary.json
coverage/histogram.html       Self-contained interactive histogram
```

Each YAML uses a separate AAPG runtime directory. This is required because AAPG
rewrites `crt.S`, `templates.S`, and linker data whenever another configuration
is generated.

## The 32 Configurations

| ID | Primary purpose |
|---|---|
| `01_rv64i_compute` | RV64I register, immediate, and word computations |
| `02_rv64i_control` | Branches, `jal`, and `jalr` |
| `03_rv64i_memory` | Integer loads and stores |
| `04_system_fence` | System, CSR, `fence`, and `fence.i` instructions |
| `05_rv64m` | Multiply, divide, and remainder operations |
| `06_rv64a_amo` | Word/doubleword AMOs and ordering bits |
| `07_rv64a_lrsc` | Directed LR/SC acquire-release user function |
| `08_rv64f` | Single-precision floating-point instructions |
| `09_rv64d` | Double-precision floating-point instructions |
| `10_fp_rounding_hazards` | F/D rounding modes and dense dependencies |
| `11_rv64c_compute_data` | Compressed compute and data instructions |
| `12_rv64c_control_stack` | Compressed control and stack instructions |
| `13_rv64imac_balanced` | Balanced I/M/A/C random mix |
| `14_rv64imafdc_balanced` | Balanced full supported ISA mix |
| `15_hazard_raw` | Forced read-after-write hazards |
| `16_hazard_war_waw` | Forced WAR and WAW hazards |
| `17_register_pressure` | Small register pool and deep lookback |
| `18_branch_forward` | Mostly forward branches |
| `19_branch_backward` | Mostly backward branches and loops |
| `20_recursion` | Recursive calls and depth stress |
| `21_icache_stress` | Instruction-cache thrashing |
| `22_dcache_stress` | Data-cache thrashing |
| `23_access_boundaries` | Multiple legal data regions and boundaries |
| `24_csr_machine_legal` | Legal machine scratch/exception CSRs |
| `25_csr_illegal_readonly` | Read-only and reserved CSR traps |
| `26_supervisor_delegation` | S-mode entry, CSRs, delegation, and ecall |
| `27_user_delegation` | U-mode entry, delegation, and ecall |
| `28_privilege_switch` | Random M/S/U transitions |
| `29_illegal_breakpoint` | Illegal instruction and breakpoint traps |
| `30_misaligned_access` | Misalignment and access-fault traps |
| `31_self_checking` | AAPG checksum self-checking mode |
| `32_long_multiseed` | 10,000-instruction full-ISA run with three seeds |

## Step 1: Place And Enter The Directory

In the virtual VS Code repository, the final location must be:

```text
~/riscv-desanv01/AAPG
```

Open a new terminal and run:

```bash
cd ~/riscv-desanv01/AAPG
pwd
ls
```

The listing must contain `Makefile`, `run_suite.py`, `cov.py`,
`suite_manifest.yaml`, and `configs/`.

## Step 2: Install The Python Requirements

Use a virtual environment so the AAPG version is reproducible:

```bash
cd ~/riscv-desanv01/AAPG
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

For later terminals, reactivate it with:

```bash
cd ~/riscv-desanv01/AAPG
source .venv/bin/activate
```

Check AAPG:

```bash
aapg version
aapg gen --help
```

## Step 3: Check Every External Tool

```bash
make toolcheck
```

Expected tools:

```text
aapg
riscv64-unknown-elf-gcc
riscv64-unknown-elf-objdump
spike
elf2hex
```

If only `elf2hex` is missing, C-Class comparison cannot run, but generation,
compilation, Spike, and coverage can still be used.

## Step 4: Regenerate And Validate The YAML Files

```bash
make configs
make validate
```

Expected validation result:

```text
PASS: validated 32 selected suite(s); manifest contains 32 suites
```

Confirm the number of files:

```bash
find configs -maxdepth 1 -name '*.yaml' | sort
find configs -maxdepth 1 -name '*.yaml' | wc -l
```

The final command must print `32`.

## Step 5: Run One Smoke Configuration First

Do not begin with all 32 configurations. First run the smallest focused flow:

```bash
make one SUITE=01_rv64i_compute SPIKE_TIMEOUT=120
```

That command performs setup, AAPG generation, GCC compilation, objdump, Spike
execution, commit dump generation, and partial coverage generation.

Check its outputs:

```bash
find work/suites/01_rv64i_compute -maxdepth 2 -type f | sort
ls -lh work/log/01_rv64i_compute__*
ls -lh work/objdump/01_rv64i_compute__*
```

After this one-suite run, `cov.xml` correctly reports one executed config and 31
missing configs. That is expected; do not use `make coverage-all` yet.

## Step 6: Run Individual Configurations

The reusable individual flow is:

```bash
make one SUITE=<suite-id> SPIKE_TIMEOUT=120
```

Examples:

```bash
make one SUITE=05_rv64m SPIKE_TIMEOUT=120
make one SUITE=10_fp_rounding_hazards SPIKE_TIMEOUT=180
make one SUITE=24_csr_machine_legal SPIKE_TIMEOUT=180
make one SUITE=31_self_checking SPIKE_TIMEOUT=180
make one SUITE=32_long_multiseed SPIKE_TIMEOUT=600
```

The runner automatically supplies `--self_checking` only for config 31 and
generates three programs with consecutive seeds only for config 32.

## Step 7: Generate And Run All 32 On Spike

Once the smoke tests pass:

```bash
cd ~/riscv-desanv01/AAPG
source .venv/bin/activate
make all SPIKE_TIMEOUT=600
```

The same workflow can be run manually in smaller stages:

```bash
make setup
make generate
make build
make spike SPIKE_TIMEOUT=600
make coverage
```

Inspect generated source and disassembly counts:

```bash
find work/suites -name '*.S' ! -name '*_template.S' | wc -l
find work/suites -name '*.riscv' | wc -l
find work/log -name '*.log' | wc -l
find work/log -name '*.dump' ! -name '*.rtl.dump' | wc -l
```

There are 34 generated programs: one from configs 1-31 and three from config 32.

## Step 8: Generate And Open Coverage

Generate reports from the current logs:

```bash
make coverage
```

Require all 32 configurations to be present:

```bash
make coverage-all
```

Validate the XML:

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('cov.xml'); print('cov.xml is valid')"
```

In the VS Code Explorer:

1. Click `cov.xml`.
2. If it opens as text, right-click it and select **Open With**.
3. Select **Functional Coverage Viewer**.
4. Expand `AAPGInstructionCoverage`.
5. Expand `<suite-id>_instructions` to see each mnemonic and frequency.
6. Expand `<suite-id>_extensions` to see I/M/A/F/D/C/System/Fence counts.

For the histogram:

1. Right-click `coverage/histogram.html`.
2. Select **Open With** and choose **Simple Browser**, **Live Preview**, or the
   available HTML preview extension.
3. Filter by YAML configuration, dynamic/static source, ISA extension, or
   mnemonic.
4. Use **Export filtered CSV** to export the current selection.

The histogram is self-contained and does not need WebGL, Plotly, or internet
access.

## Step 9: Run Spike Versus C-Class

Set the C-Class design directory:

```bash
cd ~/riscv-desanv01/AAPG
source .venv/bin/activate
export DESIGN_HOME="$PWD/../cclass_bin"
ls -lh "$DESIGN_HOME/out" "$DESIGN_HOME/boot.MSB" "$DESIGN_HOME/boot.LSB"
```

Verify one configuration first:

```bash
make run_verif SUITE=01_rv64i_compute SPIKE_TIMEOUT=120 DUT_TIMEOUT=600
```

Then run the remaining configurations individually:

```bash
make run_verif SUITE=05_rv64m SPIKE_TIMEOUT=180 DUT_TIMEOUT=900
make run_verif SUITE=08_rv64f SPIKE_TIMEOUT=180 DUT_TIMEOUT=900
make run_verif SUITE=09_rv64d SPIKE_TIMEOUT=180 DUT_TIMEOUT=900
make run_verif SUITE=28_privilege_switch SPIKE_TIMEOUT=300 DUT_TIMEOUT=1200
```

Run every configuration only after representative tests pass:

```bash
make run_verif SPIKE_TIMEOUT=600 DUT_TIMEOUT=1800
```

If generation/build/Spike were already completed and only RTL comparison is
needed:

```bash
make run_dut DUT_TIMEOUT=1800
make compare
make coverage-all
```

Successful comparison prints:

```text
PASS: <suite-and-program>; Spike and C-Class match
```

Failures create `work/log/<suite-and-program>.diff`.

## Step 10: Inspect Assembly, ELF, Disassembly, And Logs

Example for RV64M:

```bash
SUITE=05_rv64m
ls -lh work/suites/$SUITE/work/asm/$SUITE.S
ls -lh work/suites/$SUITE/work/bin/$SUITE.riscv
less work/objdump/${SUITE}__${SUITE}.objdump
less work/log/${SUITE}__${SUITE}.log
less work/log/${SUITE}__${SUITE}.dump
```

Search for an instruction:

```bash
grep -nE '\b(mul|mulh|div|rem)\b' work/objdump/05_rv64m__05_rv64m.objdump | head -30
grep -Eo '\b(mul|mulh|div|rem)[a-z.]*\b' work/log/05_rv64m__05_rv64m.log | sort | uniq -c
```

## Step 11: Interactive Spike Debugging

Build the selected suite first, then start Spike:

```bash
make debug SUITE=05_rv64m
```

Equivalent full command:

```bash
spike -d --log-commits --isa=rv64imafdczicsr_zifencei \
  work/suites/05_rv64m/work/bin/05_rv64m.riscv
```

Find symbols and addresses before entering Spike:

```bash
riscv64-unknown-elf-nm -n work/suites/05_rv64m/work/bin/05_rv64m.riscv | less
riscv64-unknown-elf-objdump -d work/suites/05_rv64m/work/bin/05_rv64m.riscv | less
```

Useful commands at the `(spike)` prompt:

```text
help                         show debugger commands
reg 0                        show integer registers for hart 0
reg 0 a0                     show one integer register
freg 0                       show floating-point registers
mem 0 0x800e0000            inspect memory at an address
until pc 0 0x80000100        run until hart 0 reaches a PC
until reg 0 a0 0x5           run until a register reaches a value
<press Enter>                execute one instruction
quit                         leave Spike
```

For config 32, select its second generated program with:

```bash
python3 run_suite.py debug --suite 32_long_multiseed --program 1
```

## Step 12: Run The Python Tests

```bash
make test
```

The tests prove that all 32 configs exist, every required AAPG section is
present, seeds/metadata are coherent, Spike lines are parsed correctly, ISA
classification works, and both XML/HTML reports are structurally valid.

## Common Problems

### `aapg: command not found`

```bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Spike or C-Class times out

Increase only the relevant timeout:

```bash
make one SUITE=32_long_multiseed SPIKE_TIMEOUT=1200
make run_verif SUITE=32_long_multiseed SPIKE_TIMEOUT=1200 DUT_TIMEOUT=3600
```

### `cov.py` reports no logs

Run Spike before coverage:

```bash
make spike SUITE=01_rv64i_compute SPIKE_TIMEOUT=120
make coverage
```

### Coverage shows fewer than 32 configurations

This means some YAML configurations have not produced dynamic `.log` files.
Read `coverage/coverage_summary.json` and inspect `missing_dynamic_suites`.

### C-Class mismatch

```bash
ls work/log/*.diff
sed -n '1,160p' work/log/<failing-name>.diff
```

The comparison normalizes the known `frm`/`fflags` ordering difference and CSR
logging differences without changing the original dumps.

