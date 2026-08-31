# AgentGate — 5-Minute Pitch Video Script

**Format:** screen recording + your voice. No slides-only. Show the real running system. Keep it under 5:00. Practice once so it flows — this doubles as your panel-interview rehearsal.

**Setup before recording:** have the live dashboard open (agentgate-ebon.vercel.app), a terminal ready in `~/Desktop/agentgate`, and the Razorpay test dashboard in another tab.

---

### 0:00–0:45 — The problem

*(On camera / voiceover over the Overview page)*

"AI agents are starting to spend real money. Razorpay just launched Agent Studio, built on the Claude Agent SDK, so agents can complete payments. Here's the question nobody's answered: what stops an agent that's been *manipulated* — by a prompt injection hidden in a product listing, a lookalike merchant, a poisoned review — from spending money it shouldn't?

This is AgentGate. It's the deterministic policy engine that sits between an AI buyer agent and the payment rails. Its core assumption is that the agent is *already compromised* — so prompt engineering is not the security boundary. This engine is. And notice: there's no LLM anywhere in the decision path."

### 0:45–2:15 — Live attack

*(Terminal: run `AGENTGATE_URL=... make demo`, or the Playground page)*

"Let me show you an attack. I'll ask the agent to buy the cheapest earbuds. There are two identical listings — the cheaper one is on a merchant called 'VoltEdgе' with a Cyrillic 'e', a homoglyph lookalike that is NOT on the mandate's allowlist.

*(agent runs; show it trying the cheap one)*

The agent, optimizing for price, tries the lookalike. Watch the gateway: **denied** — `merchant_allowed`, because the allowlist matches by merchant ID, never by name. The agent falls back to the legitimate listing, and *that* one is allowed.

*(switch to Decisions page, show the two records)*

Every decision is here, rule by rule, with its evidence and policy version. And every one — including that denial — just became a tamper-evident audit record."

### 2:15–3:15 — Metrics

*(Metrics page)*

"Here's what most submissions won't have: honest metrics. Eighty seeded scenarios, forty legitimate, forty attacks across nine classes. Recall is 100% — every attack blocked — but look here: a **14% false-positive rate**. We block roughly one in seven legitimate edge cases, like a customer genuinely reordering the same item. We don't hide that. We price it: about **₹14,000 of legitimate commerce blocked per ₹1,00,000**. That's the number a payments team actually cares about.

And these are Wilson confidence intervals, not point estimates — with three samples in a class, '100%' honestly means '44 to 100%'. We also mutation-test the rules: deliberately weaken each one and confirm the suite catches the regression. All ten caught."

### 3:15–4:00 — Architecture + trust, clicked live

*(Audit Chain page)*

"The gateway is stateless — all correctness lives in Postgres, so it doesn't depend on any one server. Spend caps are enforced under a row lock; I have a test that fires ten concurrent requests at a cap with room for one, and exactly one passes.

The audit chain — let me verify it live. *(click 'Verify chain now')* — recomputed from genesis, intact. And you don't have to trust my endpoint: *(terminal)* I export the chain and run a dependency-free verifier on my own machine — *(run `verify_chain.py`)* — same result, independently. *(click a 'replay' button)* — and any decision can be re-run to prove it's deterministic."

### 4:00–4:30 — Limitations, stated plainly

"What this does *not* do: it can't stop a colluding allowlisted merchant, or a stolen mandate key, and the 14% false-positive rate would need real fraud-data models to fix. It's a working prototype of the trust layer, not a solved fraud system. That's all written up honestly in limitations.md — because the brief says cherry-picking is insufficient, and I agree."

### 4:30–5:00 — Why Razorpay

"Authenticating an agent to a payment rail is an open problem — NPCI's UAP, Google's AP2, the Agentic Commerce Protocol are all competing on it right now. AgentGate is the layer that has to exist *regardless* of which identity standard wins: given an identified agent, bound and gate what it can do, explainably and auditably. It's built on the same Claude Agent SDK stack as Razorpay's own Agent Studio. That's the layer I want to help build. Thank you."

---

**Delivery notes:** speak to the screen, let the denials and the green 'intact' land visually. If a live call is slow, keep talking — never dead air. Total target 4:45, leaving buffer under 5:00.
