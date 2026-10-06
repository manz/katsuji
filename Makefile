.PHONY: check format

check:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy
	uv run pytest -q --cov=katsuji --cov-report=term-missing --cov-fail-under=95

format:
	uv run ruff format .
	uv run ruff check --fix .
