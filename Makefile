# Root Makefile for 3DS CFW & ROM-Hack Homebrew Suite

PROJECTS := 3ds_pokedash 3ds_sysdash 3ds_drop 3ds_wigle 3ds_rngtool 3ds_netpass 3ds_padtest 3ds_pieceduel

.PHONY: all test 3ds verify-3ds list serve scan-sd

all: test 3ds verify-3ds

test:
	@set -e; for p in $(PROJECTS); do \
		$(MAKE) -C $$p test; \
	done
	python3 -m unittest discover -s pc_companion/tests -v

3ds:
	@for p in $(PROJECTS); do \
		$(MAKE) -C $$p 3ds; \
	done

verify-3ds:
	@for p in $(PROJECTS); do \
		$(MAKE) -C $$p verify-3ds; \
	done

list:
	python3 serve_3ds.py --list

serve:
	python3 serve_3ds.py

scan-sd:
	python3 pc_companion/sd_scanner.py $(if $(URL),--url $(URL),) $(if $(SD_ROOT),--sd-root $(SD_ROOT),) $(if $(OUT),--dump-logs $(OUT),)
