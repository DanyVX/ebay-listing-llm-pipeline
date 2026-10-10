PYTHON ?= python

.PHONY: setup lint format typecheck test test-fast bench run docker-build clean privacy-scan

setup lint format typecheck test test-fast bench run docker-build clean privacy-scan:
	$(PYTHON) scripts/tasks.py $@
