.PHONY: api dash test lint migrate check

api:
	.venv/bin/uvicorn gateway.main:app --reload --port 8000

dash:
	cd dashboard && npm run dev

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check gateway/ tests/ api/ && .venv/bin/ruff format --check gateway/ tests/ api/ && .venv/bin/mypy gateway/

migrate:
	.venv/bin/alembic upgrade head

check: lint test
