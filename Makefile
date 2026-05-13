.PHONY: help install install-dev test test-quick run clean

SUBJECT ?= me
OUT     ?= report.html
CONFIG  ?= ~/.config/activity-dashboard/config.yaml

help:
	@echo "activity-dashboard — common targets"
	@echo ""
	@echo "  make install      Install runtime deps (uv sync)"
	@echo "  make install-dev  Install runtime + dev deps (adds pytest)"
	@echo "  make test         Run the full test suite (verbose)"
	@echo "  make test-quick   Run the full test suite (quiet)"
	@echo "  make run          Generate a report"
	@echo "                      Overrides: SUBJECT=alice OUT=alice.html CONFIG=path/to/config.yaml"
	@echo "  make clean        Remove .venv, caches, and build artifacts"

install:
	uv sync

install-dev:
	uv sync --extra dev

test:
	uv run pytest -v

test-quick:
	uv run pytest -q

run:
	uv run activity-dashboard --subject $(SUBJECT) --out $(OUT) --config $(CONFIG)

clean:
	rm -rf .venv .pytest_cache .mypy_cache *.egg-info build dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
