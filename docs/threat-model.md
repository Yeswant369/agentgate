# AgentGate — Threat Model (STRIDE-lite)

Every threat is cross-referenced to the **rule that mitigates it** and the **measured eval evidence** that it works — or is marked unmitigated and pointed at [limitations.md](limitations.md). A threat model tied to measured results is the difference between engineering and a feature list.

Eval evidence refers to the seeded 80-scenario suite (`make eval`, `evals/scenarios.yaml`). Detection rates carry Wilson 95% CIs; small per-class n means wide intervals, reported honestly.

## Assets

- **The mandate** — a human's scoped authorization for an agent to spend (caps, allowlist, expiry).
- **The payment rail** — the ability to create real (test-mode) Razorpay orders.
- **The audit trail** — the tamper-evident record of every decision.
- **Legitimate customers** — wrongly blocking them is a real cost (false positives).

## Threats, mitigations, evidence

| # | STRIDE | Threat | Mitigation (`rule_id` / mechanism) | Evidence |
|---|--------|--------|-----------------------------------|----------|
| 1 | Tampering | Poisoned listing injects a higher price; agent submits it | `price_integrity` — charged amount comes from our catalog, not the request | `price_manipulation` class: detection 100% [61–100%], n=6 |
| 2 | Elevation | Injection tells the agent its budget is now ₹50,00,000 | `per_txn_cap` + `daily_cap` — deterministic, agent cannot raise them | `direct_overspend` 100% [57–100%]; `over_daily_cap` 100% [51–100%] |
| 3 | Spoofing | Lookalike / homoglyph merchant impersonates an allowed one | `merchant_allowed` — allowlist matched by merchant **ID**, never by name | `off_allowlist_merchant` 100% [57–100%], includes Cyrillic lookalike |
| 4 | Elevation | Structuring: many sub-cap buys summing past the cap | `structuring` — sums recent same-merchant spend in a window | `structuring` 100% [51–100%], n=4 |
| 5 | DoS / abuse | Deny-retry loop brute-forces a blocked purchase | `velocity` — counts ALL intents incl. denials in the window | `velocity_abuse` 100% [51–100%] |
| 6 | Repudiation | Replay of a prior successful purchase intent | `duplicate_intent` + idempotency-key UNIQUE constraint | `replay_duplicate` 100% [44–100%]; webhook-replay test |
| 7 | Repudiation | Someone edits the audit log to hide a decision | Hash-chained audit; `pg_advisory_xact_lock` serializes appends | tamper test flips a row → `verify` reports broken; `verify_chain.py` independent |
| 8 | Tampering | Forged / replayed Razorpay webhook | HMAC constant-time verify + event-id dedupe; amount cross-checked vs ledger | webhook signature + triple-delivery tests |
| 9 | Elevation | Use of an expired or revoked mandate | `mandate_active` — revoked/expired checked against DB time | `revoked_mandate`, `expired_mandate` 100% [44–100%] each |
| 10 | Info disclosure | Deny response leaks policy internals to the agent | Agent gets rule ids + reasons only; full evidence stays in the audit log | `intents._deny_reasons` |
| 11 | DoS | Public playground abused to exhaust the gateway | DB-backed per-IP rate limit (20/min) — bounded and gated, the thesis applied to itself | `ratelimit` + 429 path |
| 12 | Availability | Infra failure could fail *open* and approve | Fail-closed: any error → `system_error` deny, logged; never approve on crash | fail-closed test kills DB mid-request → 503 deny |

## Unmitigated (honest gaps → [limitations.md](limitations.md))

| STRIDE | Threat | Why unmitigated |
|--------|--------|----------------|
| Spoofing | **Stolen mandate key** | The agent key is a bearer credential; we hash it at rest and scope it tightly, but do not detect anomalous *use* (no device binding, no behavioral baseline). |
| Collusion | **Malicious allowlisted merchant + compromised agent** | A correctly-priced purchase to an *allowed* merchant passes every rule. We assume allowlisted merchants are honest. |
| Elevation | **Model-level jailbreak** | Irrelevant to the decision path (no LLM there), but it means line-1 defense can be fully defeated; if an attack reduces to a rule-compliant purchase, no gateway logic stops it. |
| Cost | **False positives on legitimate edge cases** | Measured at ~14% FPR (≈ ₹14,286 per ₹1L). Deterministic thresholds cannot tell a legit bulk-buyer from a structuring attacker; production needs per-user risk models. |

## What the evidence does and does not prove

100% detection on this suite means every attack **we encoded** is blocked — a floor, not a ceiling. Real adversaries adapt; the wide confidence intervals (n=3–6 per class) are the honest statement of how much we actually know. The value here is a *measured, reproducible, mutation-tested* baseline — not a claim of production-grade safety.
