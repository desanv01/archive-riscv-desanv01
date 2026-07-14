# Run RISC-V Tests


---

# Compile and Run Tests on Spike

## Default mode (p-mode)

To compile and run a test in physical mode:

```bash
make run TEST=<path/to/test_file.S> MODE=p
```

Example:

```bash
make run TEST=./tests/add.S MODE=p
```

---

## Virtual mode (v-mode)

To compile and run a test in virtual memory mode:

```bash
make run TEST=<path/to/test_file.S> MODE=v
```

Example:

```bash
make run TEST=./tests/add.S MODE=v
```

---

# Run Only on Spike

Run an already compiled ELF on Spike:

```bash
make spike TEST=<path/to/test_file.S> MODE=<p|v>
```

Example:

```bash
make spike TEST=./tests/add.S MODE=v
```
---

# Generate Disassembly

Generate objdump disassembly:

```bash
make disasm TEST=<path/to/test_file.S> MODE=<p|v>
```

Example:

```bash
make disasm TEST=./tests/add.S MODE=v
```

---

# Run Complete Verification Flow (Spike + RTL + Compare)

## Setup C-Class binaries

Set C-Class executable location:

```bash
export DESIGN_HOME=<path/to/cclass/bin>
```

---

Command:

```bash
make run_verif TEST=<path/to/test_file.S> MODE=<p|v>
```

Examples:

### Physical mode

```bash
make run_verif TEST=./tests/add.S MODE=p
```

### Virtual mode

```bash
make run_verif TEST=./tests/add.S MODE=v
```

---

# Compare Spike and RTL Dumps

To compare dumps manually:

```bash
make compare TEST=<path/to/test_file.S> MODE=<p|v>
```

Example:

```bash
make compare TEST=./tests/add.S MODE=v
```
---

# Clean Work Directory

Remove generated files:

```bash
make clean TEST=<testname> MODE=<p|v>
```

Example:

```bash
make clean TEST=./tests/add MODE=v
```

---
