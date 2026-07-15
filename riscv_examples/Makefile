# Makefile for compiling and verifying RISC-V tests on Spike and DUT

ifndef TEST
$(error TEST is not set. Example: make run_verif TEST=./tests/add.S MODE=v)
endif

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

MODE ?= p

FILENAME  := $(basename $(notdir $(TEST)))
TEST_HOME := $(CURDIR)
OUT_DIR   := $(TEST_HOME)/work/$(MODE)/$(FILENAME)

# -----------------------------------------------------------------------------
# Tools and timeouts
# -----------------------------------------------------------------------------

GCC       := riscv64-unknown-elf-gcc
OBJDUMP   := riscv64-unknown-elf-objdump
SPIKE     := spike

# Small tests finish quickly, but exhaustive tests generate very large dumps.
SPIKE_TIMEOUT ?= 180s
RTL_TIMEOUT   ?= 900s

TIMEOUT := timeout --foreground $(SPIKE_TIMEOUT)

# -----------------------------------------------------------------------------
# Mode Selection
#
# MODE=p -> normal physical-memory environment
# MODE=v -> virtual-memory environment
# -----------------------------------------------------------------------------

ifeq ($(MODE),v)
RTL_SKIP_LINES := 13
else
RTL_SKIP_LINES := 4
endif

ifeq ($(MODE),v)

CFLAGS := -march=rv64imafdczicsr_zifencei \
          -mabi=lp64 \
          -static \
          -mcmodel=medany \
          -fvisibility=hidden \
          -nostdlib \
          -nostartfiles \
          -DENTROPY=0x9629af2 \
          -std=gnu99 \
          -O2 \
          -I$(TEST_HOME)/env/v \
          -I$(TEST_HOME)/isa/macros/scalar \
          -T$(TEST_HOME)/env/v/link.ld

EXTRA_FILES := $(TEST_HOME)/env/v/entry.S \
               $(TEST_HOME)/env/v/*.c

else

CFLAGS := -march=rv64imafdczicsr_zifencei \
          -mabi=lp64 \
          -static \
          -mcmodel=medany \
          -fvisibility=hidden \
          -nostdlib \
          -nostartfiles \
          -DENTROPY=0x9629af2 \
          -std=gnu99 \
          -O2 \
          -I$(TEST_HOME)/env \
          -T$(TEST_HOME)/env/link.ld

EXTRA_FILES :=

endif

.PHONY: all run disasm spike run_dut compare run_verif clean

all: run

# -----------------------------------------------------------------------------
# Compile
# -----------------------------------------------------------------------------

run: $(OUT_DIR)/$(FILENAME).elf
	@$(MAKE) --no-print-directory disasm MODE=$(MODE)
	@$(MAKE) --no-print-directory spike MODE=$(MODE)
	@echo "-------------------------------------------------------------------------"
	@echo "DONE"
	@echo "-------------------------------------------------------------------------"

$(OUT_DIR)/$(FILENAME).elf: $(TEST)
	@echo "-------------------------------------------------------------------------"
	@echo "Compiling $(TEST)"
	@echo "MODE = $(MODE)"
	@echo "-------------------------------------------------------------------------"
	mkdir -p $(OUT_DIR)
	rm -rf $(OUT_DIR)/*
	$(GCC) $(CFLAGS) \
		$(EXTRA_FILES) \
		$< \
		-o $@

# -----------------------------------------------------------------------------
# Disassembly
# -----------------------------------------------------------------------------

disasm: $(OUT_DIR)/$(FILENAME).elf
	@echo "-------------------------------------------------------------------------"
	@echo "Disassembly Generation"
	@echo "-------------------------------------------------------------------------"
	$(OBJDUMP) --disassemble-all --disassemble-zeroes \
		--section=.text \
		--section=.text.startup \
		--section=.text.init \
		--section=.data \
		$< > $(OUT_DIR)/$(FILENAME).disass

# -----------------------------------------------------------------------------
# Spike Run
# -----------------------------------------------------------------------------

spike: $(OUT_DIR)/$(FILENAME).elf
	@echo "-------------------------------------------------------------------------"
	@echo "Running on Spike"
	@echo "Spike timeout = $(SPIKE_TIMEOUT)"
	@echo "-------------------------------------------------------------------------"
	$(TIMEOUT) $(SPIKE) \
		--log-commits \
		--log $(OUT_DIR)/$(FILENAME).dump \
		--isa=rv64gcZicsr_Zifencei \
		+signature=spike_signature.txt \
		+signature-granularity=4 \
		$<

# -----------------------------------------------------------------------------
# C-Class RTL Run
# -----------------------------------------------------------------------------

run_dut: $(OUT_DIR)/$(FILENAME).elf
	@if [ -z "$(DESIGN_HOME)" ]; then \
		echo "ERROR: DESIGN_HOME is not set."; \
		echo 'Run: export DESIGN_HOME="$$PWD/../cclass_bin"'; \
		exit 1; \
	fi
	@if [ ! -x "$(DESIGN_HOME)/out" ]; then \
		echo "ERROR: $(DESIGN_HOME)/out was not found or is not executable."; \
		exit 1; \
	fi
	@echo "-------------------------------------------------------------------------"
	@echo "Running Tests on C-CLASS"
	@echo "RTL timeout = $(RTL_TIMEOUT)"
	@echo "-------------------------------------------------------------------------"
	@echo "Copying design files from $(DESIGN_HOME)"
	cp -r "$(DESIGN_HOME)"/. $(OUT_DIR)/
	elf2hex 8 4194304 \
		$(OUT_DIR)/$(FILENAME).elf \
		2147483648 \
		> $(OUT_DIR)/code.mem
	cd $(OUT_DIR) && \
		timeout --foreground $(RTL_TIMEOUT) ./out +rtldump
	@echo "-------------------------------------------------------------------------"
	@echo "RTL RUN COMPLETED"
	@echo "-------------------------------------------------------------------------"

# -----------------------------------------------------------------------------
# Compare Spike and RTL Dumps
# -----------------------------------------------------------------------------

compare:
	@echo "-------------------------------------------------------------------------"
	@echo "Comparing Spike and RTL Dumps"
	@echo "-------------------------------------------------------------------------"

	@test -f "$(OUT_DIR)/$(FILENAME).dump" || { \
		echo "ERROR: Spike dump not found."; \
		exit 1; \
	}

	@test -f "$(OUT_DIR)/rtl.dump" || { \
		echo "ERROR: RTL dump not found."; \
		exit 1; \
	}

	@head -n -$(RTL_SKIP_LINES) \
		$(OUT_DIR)/rtl.dump \
		> $(OUT_DIR)/rtl.trimmed.dump

	@sed -E \
		's/c2_frm (0x[0-9a-fA-F]+) c1_fflags (0x[0-9a-fA-F]+)/c1_fflags \2 c2_frm \1/g' \
		$(OUT_DIR)/$(FILENAME).dump \
		> $(OUT_DIR)/spike.normalized.dump

	@sed -E \
		's/c2_frm (0x[0-9a-fA-F]+) c1_fflags (0x[0-9a-fA-F]+)/c1_fflags \2 c2_frm \1/g' \
		$(OUT_DIR)/rtl.trimmed.dump \
		> $(OUT_DIR)/rtl.normalized.dump

	@diff -iwu \
		$(OUT_DIR)/spike.normalized.dump \
		$(OUT_DIR)/rtl.normalized.dump \
		> $(OUT_DIR)/dump.diff || true

	@if [ -s "$(OUT_DIR)/dump.diff" ]; then \
		echo "FAIL : Spike and RTL mismatch"; \
		echo "See $(OUT_DIR)/dump.diff"; \
		exit 1; \
	else \
		echo "PASS : Spike and RTL match"; \
		rm -f $(OUT_DIR)/dump.diff; \
	fi

# -----------------------------------------------------------------------------
# Full Verification Flow
# -----------------------------------------------------------------------------

run_verif:
	@$(MAKE) --no-print-directory \
		$(OUT_DIR)/$(FILENAME).elf MODE=$(MODE)

	@$(MAKE) --no-print-directory \
		disasm MODE=$(MODE)

	@$(MAKE) --no-print-directory \
		spike MODE=$(MODE)

	@$(MAKE) --no-print-directory \
		run_dut MODE=$(MODE)

	@$(MAKE) --no-print-directory \
		compare MODE=$(MODE)

	@echo "-------------------------------------------------------------------------"
	@echo "VERIFICATION COMPLETED SUCCESSFULLY"
	@echo "-------------------------------------------------------------------------"

# -----------------------------------------------------------------------------
# Clean
# -----------------------------------------------------------------------------

clean:
	@echo "Cleaning $(OUT_DIR)"
	rm -rf $(OUT_DIR)
