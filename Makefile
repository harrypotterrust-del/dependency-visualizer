PYTHON ?= python3
export PYTHON
export PYTHONPATH := src

.PHONY: run test lint check demo

run:
	$(PYTHON) -m depviz $(ARGS)

test:
	$(PYTHON) -m pytest -q tests

lint:
	$(PYTHON) -m flake8 src tests

check: lint test

demo:
	./scripts/demo_ok.sh
	./scripts/demo_errors.sh
