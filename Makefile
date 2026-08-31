.PHONY: api dash test lint migrate check seed seed-attacks reconcile e2e demo eval fixtures

api:
	.venv/bin/uvicorn gateway.main:app --reload --port 8000

dash:
	cd dashboard && npm run dev

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check gateway/ tests/ scripts/ api/ && .venv/bin/ruff format --check gateway/ tests/ scripts/ api/ && .venv/bin/mypy gateway/

migrate:
	.venv/bin/alembic upgrade head

seed:
	.venv/bin/python scripts/seed_catalog.py

seed-attacks:
	.venv/bin/python scripts/seed_attacks.py

demo:
	.venv/bin/python scripts/demo.py

eval:
	.venv/bin/python -m evals.run

fixtures:
	.venv/bin/python -m evals.dump_fixtures

reconcile:
	.venv/bin/python scripts/reconcile.py

e2e:
	.venv/bin/python scripts/e2e_smoke.py

check: lint test
