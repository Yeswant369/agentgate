# AgentGate

**A trust gateway for agentic commerce.** AI agents are starting to spend real money. AgentGate is the deterministic policy engine that stands between an AI buyer agent and the payment rails (Razorpay): every money action explainable, bounded and gated — even when the agent itself has been manipulated.

> Security model in one line: the gateway assumes the agent is already compromised. Prompt engineering is not the security boundary — this engine is.

**Live demo:** _URL coming after first deploy_ · **Build plan:** [docs/build-plan.md](docs/build-plan.md)

## Quickstart (local, ~5 minutes)

Requirements: Python 3.12+ · Node 22+ · a free [Neon](https://neon.tech) Postgres database.

```bash
git clone <this repo> && cd agentgate
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL (Neon pooled string)
make migrate                # apply database migrations
make api                    # FastAPI on :8000  (docs at /api/docs)
make dash                   # in a second terminal: Vite dev server on :5173
```

Open http://localhost:5173 — the header badge goes green when the gateway reports ready.

## Commands

| Command | What it does |
|---|---|
| `make test` | Run the test suite |
| `make lint` | ruff + mypy |
| `make check` | lint + tests (what CI runs) |
| `make migrate` | Apply Alembic migrations to `DATABASE_URL` |

## Architecture (Phase 1)

- **FastAPI gateway** — deployed as a single Vercel Fluid Compute function (`api/index.py`), stateless by design: all correctness state lives in Postgres, never in process memory.
- **Vite + React dashboard** — static files on the same Vercel domain; `/api/*` rewrites to the gateway function.
- **Neon Postgres** — via SQLAlchemy 2.0 + Alembic; pooled connection string.
- **Observability from day one** — request-ID middleware on every request, structured JSON logs, RFC 7807 `problem+json` error envelope on every error path, liveness (`/api/health/live`) split from readiness (`/api/health/ready`).

## Deploy (Vercel)

1. Push this repo to GitHub and import it in Vercel (framework preset: Other — `vercel.json` drives the build).
2. Set env vars in Vercel: `ENV=production`, `DATABASE_URL` (Neon **pooled** string with the `postgresql+psycopg://` scheme).
3. Run migrations from your laptop: `make migrate` (migrations never run inside the function).
4. Confirm Fluid Compute is enabled (it is the default) and open `/api/health/ready`.

## Status

Phase 1 of 6 — walking skeleton. See [docs/build-plan.md](docs/build-plan.md) for the full roadmap: money rails → policy engine + audit chain → buyer agent + hostile marketplace → adversarial evals → judge playground.

---
Built with Claude Code for the Razorpay AI Buildathon (Track 1: AI Growth & Agentic Commerce).
