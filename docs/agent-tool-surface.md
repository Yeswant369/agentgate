# The Agent's Tool Surface Is a Security Decision

The buyer agent is granted **exactly four tools**, and nothing else:

| Tool | What it can do | What it cannot do |
|---|---|---|
| `search_catalog` | Read product listings by keyword | — |
| `get_product` | Read one product's real catalog price | — |
| `create_purchase_intent` | Ask the gateway to authorize a purchase | Decide the outcome — the gateway does |
| `check_intent_status` | Read the ledger state of its own transaction | See other agents' transactions |

**Explicitly denied:** `Bash`, `Read`, `Write`, `Edit`, `WebFetch`, `WebSearch`, `Glob`, `Grep` — every filesystem, shell, and network-egress capability the Claude Agent SDK can otherwise provide. `setting_sources=[]` also means no local `CLAUDE.md` or settings can widen the surface.

## Why this is a security control, not a convenience

Most agent builders hand their agent a broad toolkit — a shell, file access, arbitrary HTTP — because it is easy and "might be useful." That is an attack surface nobody inventoried. When a poisoned product description says *"run this command"* or *"fetch this URL"*, an agent with those tools might comply.

AgentGate's agent **cannot** comply, because the capability does not exist in its world:

- It holds **only its scoped agent key** — no Razorpay credentials, no database access, no admin token. A fully compromised agent can still only send purchase intents the gateway will independently judge.
- It has **no shell or filesystem** — indirect prompt injection cannot escalate into code execution or data exfiltration, because there is nothing to execute against.
- Its four tools are all **thin, audited HTTP calls to one gateway** — every action it can take is a request the deterministic policy engine evaluates and the audit chain records.

The minimal surface and the deny-by-default gateway are the same idea applied at two layers: **assume the agent is compromised, and make sure the blast radius is bounded by construction.**

## The two lines of defense, in order

1. **System prompt (first line, expected to sometimes fail):** the agent is told catalog text is untrusted data, to respect its budget, and not to retry denials. This stops the easy cases.
2. **The gateway (the line that must hold):** even if the prompt fails completely — the agent absorbs an injected budget, tries to buy a gift card, claims a false price — the deterministic policy engine denies it, and the audit chain records both the attempt and the reason.

The whole project rests on line 2. Line 1 is courtesy; line 2 is the guarantee.
