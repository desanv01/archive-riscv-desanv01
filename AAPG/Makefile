# AAPG 32-suite generation, Spike execution, C-Class comparison, and coverage.

PYTHON ?= python3
SUITE ?=
SPIKE_TIMEOUT ?= 60
DUT_TIMEOUT ?= 600
RTL_SKIP_LINES ?= 4

SELECT := $(if $(strip $(SUITE)),--suite $(SUITE),)
TIMEOUTS := --spike-timeout $(SPIKE_TIMEOUT) --dut-timeout $(DUT_TIMEOUT) --rtl-skip-lines $(RTL_SKIP_LINES)

.PHONY: help configs validate toolcheck setup generate build spike coverage coverage-all \
	one all run_dut compare run_verif debug test clean clean-reports

help:
	@echo "AAPG 32-suite workflow"
	@echo "  make configs                 Regenerate all 32 full YAML configs"
	@echo "  make validate                Validate manifest and YAML schemas"
	@echo "  make toolcheck               Check AAPG/RISC-V/Spike/elf2hex tools"
	@echo "  make one SUITE=<id>          Generate, build, run Spike, and report one suite"
	@echo "  make all                     Generate/build/run all suites on Spike and report"
	@echo "  make run_verif SUITE=<id>    Spike versus C-Class verification"
	@echo "  make run_verif               Verify every suite on Spike and C-Class"
	@echo "  make debug SUITE=<id>        Start interactive spike -d for one built suite"
	@echo "  make coverage                Rebuild cov.xml and interactive histogram"
	@echo "  make coverage-all            Require dynamic logs for all 32 configs"

configs:
	$(PYTHON) generate_configs.py

validate:
	$(PYTHON) run_suite.py validate $(SELECT)

toolcheck:
	$(PYTHON) run_suite.py toolcheck

setup:
	$(PYTHON) run_suite.py setup $(SELECT)

generate:
	$(PYTHON) run_suite.py generate $(SELECT)

build:
	$(PYTHON) run_suite.py build $(SELECT)

spike:
	$(PYTHON) run_suite.py spike $(SELECT) --spike-timeout $(SPIKE_TIMEOUT)

coverage:
	$(PYTHON) cov.py

coverage-all:
	$(PYTHON) cov.py --require-all

one:
	@test -n "$(SUITE)" || (echo "ERROR: use make one SUITE=01_rv64i_compute"; exit 1)
	$(PYTHON) generate_configs.py
	$(PYTHON) run_suite.py validate $(SELECT)
	$(PYTHON) run_suite.py setup $(SELECT)
	$(PYTHON) run_suite.py generate $(SELECT)
	$(PYTHON) run_suite.py build $(SELECT)
	$(PYTHON) run_suite.py spike $(SELECT) --spike-timeout $(SPIKE_TIMEOUT)
	$(PYTHON) cov.py

all:
	$(MAKE) configs
	$(MAKE) validate
	$(MAKE) toolcheck
	$(MAKE) setup
	$(MAKE) generate
	$(MAKE) build
	$(MAKE) spike SPIKE_TIMEOUT=$(SPIKE_TIMEOUT)
	$(MAKE) coverage

run_dut:
	$(PYTHON) run_suite.py dut $(SELECT) --dut-timeout $(DUT_TIMEOUT)

compare:
	$(PYTHON) run_suite.py compare $(SELECT) --rtl-skip-lines $(RTL_SKIP_LINES)

run_verif:
	$(PYTHON) run_suite.py verify $(SELECT) $(TIMEOUTS)
	$(PYTHON) cov.py

debug:
	@test -n "$(SUITE)" || (echo "ERROR: use make debug SUITE=01_rv64i_compute"; exit 1)
	$(PYTHON) run_suite.py debug $(SELECT)

test:
	$(PYTHON) -m unittest discover -s tests -v

clean-reports:
	rm -rf cov.xml coverage

clean:
	rm -rf work cov.xml coverage

