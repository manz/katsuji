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

publish: check
	rm -rf dist
	uv build
	HATCH_INDEX_USER=$(HATCH_INDEX_USER) HATCH_INDEX_AUTH=$(HATCH_INDEX_AUTH) uvx hatch publish
