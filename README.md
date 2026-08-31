# AgentGate

**A trust gateway for agentic commerce.** AI agents are starting to spend real money — Razorpay's Agent Studio, built on the Claude Agent SDK, already lets agents complete payments. AgentGate is the deterministic policy engine that sits between an AI buyer agent and the payment rails (Razorpay), making **every money action explainable, bounded and gated — even when the agent itself has been manipulated** by a prompt injection, a lookalike merchant, or a poisoned listing.

> **Security model in one line:** the gateway assumes the agent is already compromised. Prompt engineering is not the security boundary — this engine is. There is no LLM anywhere in the decision path.

**🔗 Live demo:** [agentgate-ebon.vercel.app](https://agentgate-ebon.vercel.app) · **API docs:** [/api/docs](https://agentgate-ebon.vercel.app/api/docs) · **Verify the audit chain yourself:** [/api/audit/export](https://agentgate-ebon.vercel.app/api/audit/export)

*Razorpay AI Buildathon — Track 1: AI Growth & Agentic Commerce*

---

## 60-second tour

| Page | What it shows |
|---|---|
| **[Overview](https://agentgate-ebon.vercel.app/)** | The thesis, live decision counters, denials by rule, audit-chain integrity badge. |
| **[Decisions](https://agentgate-ebon.vercel.app/decisions)** | Every gateway verdict, rule by rule, with evidence and a per-decision **replay** button. This page *is* the "explainable" criterion. |
| **[Metrics](https://agentgate-ebon.vercel.app/metrics)** | Confusion matrix, per-class detection with 95% CIs, false-positive cost in ₹, mutation-testing status. |
| **[Audit Chain](https://agentgate-ebon.vercel.app/audit)** | Hash-chained log + live "Verify chain now". |
| **[Playground](https://agentgate-ebon.vercel.app/playground)** | Click to re-fire recorded attacks through the **live** policy engine. Rate-limited — the demo is itself bounded and gated. |

## Measured results (reproducible with `make eval`)

Seeded 80-scenario suite (40 legitimate, 40 attacks across 9 classes):

- **Recall 100% [91–100%]** — every encoded attack blocked.
- **False-positive rate 14% [6–29%]** — we honestly block some legitimate edge cases and measure the cost.
- **FP cost ≈ ₹14,286** of legitimate commerce blocked per ₹1,00,000 of legitimate agent commerce.
- **10 policy mutations, all caught** — the rule suite is proven to actually test something.

The 14% false-positive rate is deliberate honesty: a gateway that blocks everything has perfect recall and is worthless. See **[docs/limitations.md](docs/limitations.md)**.

## What makes it hold

- **Deterministic, LLM-free decision path** — 10 pure policy rules; a jailbroken agent can't argue with a comparison.
- **Deny-by-default & fail-closed** — any error → `system_error` deny, recorded. An unavailable gateway never approves. *(Tested.)*
- **Race-proof spend caps** — `SELECT … FOR UPDATE`; 10 concurrent requests at a cap with room for one → exactly one passes. *(Tested.)*
- **Hash-chained audit log** — tamper-evident; verify it **without trusting us**: `curl .../api/audit/export > chain.json && python3 scripts/verify_chain.py chain.json`.
- **Integer paise everywhere** · **HMAC-verified, replay-safe webhooks** · **structuring / velocity / price-injection / lookalike-merchant defenses** · **stateless gateway, all correctness in Postgres**.

## Try the live agent yourself

The buyer agent runs locally on the Claude Agent SDK (no API key — it uses your Claude login) and talks to the deployed gateway:

```bash
AGENTGATE_URL=https://agentgate-ebon.vercel.app make demo
```

It runs a legit purchase (allowed) and a lookalike-merchant attack (denied, then falls back to the real listing), printing both verdicts. Watch them appear on the [Decisions](https://agentgate-ebon.vercel.app/decisions) page.

## Quickstart (local, ~5 minutes)

Requirements: Python 3.12+ · Node 22+ · a free [Neon](https://neon.tech) Postgres database · Razorpay test-mode keys.

```bash
git clone <this repo> && cd agentgate
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL, Razorpay test keys, ADMIN_TOKEN
make migrate                # apply migrations
make seed && make seed-attacks   # catalog + poisoned listings
make api                    # FastAPI on :8000 (docs at /api/docs)
make dash                   # second terminal: dashboard on :5173
make eval                   # generate metrics
```

| Command | Does |
|---|---|
| `make demo` | Run the real agent through a legit purchase + an attack |
| `make eval` | Run the 80-scenario eval, print metrics, persist a run |
| `make test` | 79 tests |
| `make check` | lint + typecheck + tests (what CI runs) |
| `make reconcile` | Diff our ledger against Razorpay's records |

## Documentation

- **[Architecture](docs/architecture.md)** — system diagram, trust boundaries, security model, tech choices, UAP/AP2/ACP positioning.
- **[Threat model](docs/threat-model.md)** — STRIDE-lite, each threat tied to a rule and its measured eval evidence.
- **[Limitations](docs/limitations.md)** — the honest failure analysis: real false positives, uncovered attack classes, what production needs.
- **[Build plan](docs/build-plan.md)** — the 6-phase roadmap this was built against.
- **[Agent tool surface](docs/agent-tool-surface.md)** — why the agent gets exactly four tools.

## Stack

FastAPI (Python 3.12) on Vercel Fluid Compute · Neon Postgres (all correctness state) · Razorpay test-mode APIs · Claude Agent SDK buyer agent (local) · Vite + React dashboard · CI on every push (lint, types, tests, eval regression + mutation gate).

---
Built with [Claude Code](https://claude.com/claude-code) for the Razorpay AI Buildathon. The engineering decisions, security model, and honest metrics are the substance; Claude Code was the pair-programmer that helped build and test it.
