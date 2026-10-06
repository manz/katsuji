.PHONY: check tests format publish

check:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy
	uv run pytest -q --cov=katsuji --cov-report=term-missing --cov-fail-under=95

# The pre-push hook runs `make tests`.
tests: check

format:
	uv run ruff format .
	uv run ruff check --fix .

# Same credentials as a816's `make publish`: HATCH_INDEX_USER / HATCH_INDEX_AUTH.
publish: check
	rm -rf dist
	uv build
	uv publish --username "$(HATCH_INDEX_USER)" --password "$(HATCH_INDEX_AUTH)"
