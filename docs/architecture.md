# AgentGate — Architecture

## The problem

AI agents are beginning to transact autonomously. Razorpay's own Agent Studio (built on the Claude Agent SDK) lets businesses deploy agents that complete payments. The open question underneath all of it: **how do you let an AI agent spend money safely when the agent can be manipulated** — by a prompt injection hidden in a product listing, a poisoned review, a lookalike merchant? AgentGate is a working prototype of that control layer.

## The security model (the load-bearing idea)

**Assume the agent is already compromised.** The gateway is designed to hold even if the buyer agent is fully cooperating with an attacker. That single assumption drives every decision below:

- **The decision path contains no LLM.** Policy is a pipeline of pure, deterministic Python functions. When someone asks "what if the model misbehaves?", the answer is: the thing that decides has no model in it. A jailbroken agent cannot argue with a `>` comparison.
- **Deny-by-default.** Every rule must pass; the first deny wins. New situations fail closed, not open.
- **Fail closed.** If the database, the policy engine, or spend accounting errors out, the answer is *deny* with `rule_id=system_error`, recorded in the audit log. An unavailable gateway never approves. (Tested: a simulated infrastructure failure mid-request returns a fail-closed denial.)
- **Two lines of defense, and only the second is trusted.** The agent's system prompt (treat catalog text as data, respect the budget) is line 1 — courtesy, expected to sometimes fail. The deterministic gateway is line 2 — the guarantee.

## System diagram and trust boundaries

```
  ┌─────────────────────────────┐
  │  UNTRUSTED                   │        the agent holds ONLY its scoped
  │  ┌───────────────────────┐   │        agent key — no Razorpay creds,
  │  │  Claude buyer agent    │   │        no DB access, no shell/filesystem
  │  │  (Claude Agent SDK,    │   │
  │  │   4 tools, local)      │   │
  │  └───────────┬───────────┘   │
  └──────────────┼───────────────┘
                 │  HTTPS + X-Agent-Key      ← TRUST BOUNDARY
  ┌──────────────▼───────────────────────────────────────────┐
  │  TRUSTED — AgentGate gateway (FastAPI on Vercel)          │
  │                                                           │
  │   authenticate → LOCK mandate row → gather inputs →       │
  │   deterministic policy pipeline (10 rules) →              │
  │   verdict {allow | deny | step_up} →                      │
  │   append hash-chained audit record →                      │
  │   on allow: create Razorpay order                         │
  │                                                           │
  └───────────┬───────────────────────────────┬──────────────┘
              │                                │
   ┌──────────▼──────────┐        ┌────────────▼─────────────┐
   │  Neon Postgres       │        │  Razorpay (test mode)     │
   │  ALL correctness      │        │  orders, refunds,         │
   │  state lives here:    │        │  HMAC-verified webhooks   │
   │  mandates, ledger,    │        └───────────────────────────┘
   │  audit chain, spend,  │
   │  rate limits          │        Dashboard (read-only evidence) is served
   └──────────────────────┘        from the same Vercel domain; humans browse,
                                    they do not transact.
```

## Why stateless + durable Postgres

The gateway is a single Vercel Fluid Compute function — stateless, horizontally scaled, instances recycled freely. **No correctness ever lives in process memory.** Spend accounting, idempotency, velocity windows, rate limits, and the audit chain are all in Postgres. This is deliberate and defensible:

> "The trust gateway is intentionally stateless. Authorization, replay protection, idempotency and audit state are enforced durably in PostgreSQL, so correctness doesn't depend on any individual compute instance."

Concurrency safety is real, not hoped-for: spend caps are enforced under a `SELECT … FOR UPDATE` row lock on the mandate (the 10-concurrent-requests test proves exactly one of ten passes a cap with room for one); audit appends are serialized under a `pg_advisory_xact_lock` so the hash chain cannot fork. Because state is durable and portable, the gateway can move to a long-running container (Railway) with a config change if a persistent worker is ever needed.

## The audit chain

Every decision — allow, deny, step_up, and system-error alike — appends a record whose hash covers `sha256(prev_hash + canonical_json(content))`. Tampering with any historical row breaks every hash after it. `/api/audit/verify` recomputes the whole chain server-side; `/api/audit/export` + the dependency-free `scripts/verify_chain.py` let a judge recompute it on their own machine, trusting no endpoint of ours. It is a hash chain in Postgres, not a blockchain — tamper-evidence is what an audit trail needs, and consensus infrastructure would add nothing.

## Tech choices, with reasons

| Choice | Why |
|---|---|
| **Python / FastAPI** | The eval/metrics work is native to Python; one language the author can defend line-by-line in a panel. Auto-generated OpenAPI docs at `/api/docs` let judges poke the API. |
| **Vercel Fluid Compute** | Free Hobby tier, always-warm instance reuse, single domain (no CORS). Verified against 2026 docs before choosing. Host-portable by design. |
| **Neon Postgres** | Serverless Postgres holding all correctness state; pooled connection composes with transaction-scoped locks. |
| **Claude Agent SDK** | The exact stack Razorpay's Agent Studio uses. Runs on the author's existing Claude login — no API key, no per-token cost. Four custom tools only; the minimal tool surface is a security control. |
| **Deterministic policy engine** | Auditability and replayability require determinism; an LLM in the decision path would forfeit both. |
| **Integer paise everywhere** | One float in a money path is disqualifying at a payments company. |

## Where this sits in the agentic-payments landscape

Authenticating an autonomous agent to a payment rail is an unsolved industry problem with competing emerging standards: **NPCI's UAP**, Google's **Agent Payments Protocol (AP2)**, and the **Agentic Commerce Protocol (ACP)**. AgentGate's mandate-bound agent key is a stand-in for agent-identity infrastructure that does not yet exist at standard. The gateway's contribution is orthogonal and complementary: *given* an identified agent, bound and gate what it can do, explainably. That is the layer that has to exist regardless of which identity standard wins — and it is the layer this project builds and measures. See [limitations.md](limitations.md) for what production would additionally require.
