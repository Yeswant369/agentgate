# Limitations & Honest Failure Analysis

The Razorpay brief states plainly that cherry-picked examples are insufficient and that honest metrics — including false-positive cost — are required. This document is that honesty. It records where AgentGate's gateway succeeds, where it *fails*, and what a production system would need that this prototype does not have.

If you only read one thing: **AgentGate is a working prototype of a trust layer, not a solved fraud system.** The eval numbers below are real, reproducible (`make eval`), and include the cases where we block legitimate customers.

## What the measured results actually say

On the seeded 80-scenario suite (40 legitimate, 40 attacks across 9 classes):

- **Recall 100% [91–100%]** — every attack in the suite is blocked. But this is measured against attacks *we thought of and encoded*. Real adversaries adapt; a 100% on a fixed suite is a floor, not a ceiling of safety.
- **False-positive rate ~14% [6–29%]** — we block roughly one in seven legitimate edge-case purchases. This is not a rounding error; it is a real cost, priced below.
- **False-positive cost ≈ ₹14,286 per ₹1,00,000** of legitimate agent commerce blocked. At Razorpay scale this would be unacceptable and would require tuning against real transaction data we do not have.

The confidence intervals are wide because n≈40 per aggregate and n=3–6 per attack class. **A per-class "100%" with n=3 means [44–100%] — we genuinely do not know the true detection rate for those classes.** Reporting the interval instead of the point estimate is the honest thing to do.

## Where we knowingly block good customers (real false positives)

These are in the scenario set on purpose, with ground truth "should allow":

1. **Legitimate repeat purchases** (`legit_fp_repeat_purchase`, `legit_fp_second_same_item`) — a customer who genuinely reorders the same item, or buys two identical units as gifts, trips `duplicate_intent`. The rule that stops replay abuse cannot tell a replay from a real reorder.
2. **Legitimate bulk shopping** (`legit_fp_bulk_shopping`, `legit_fp_stocking_up`) — a customer buying several items from one merchant in an hour trips `structuring`. The salami-slicing detector cannot distinguish a fraud pattern from an enthusiastic shopper.
3. **Fast browsing-and-buying** (`legit_fp_fast_browsing`) — a burst of small legitimate purchases trips `velocity`.

**Root cause:** these rules are deterministic thresholds with no notion of customer history, reputation, or intent. Production fraud systems resolve this with per-user risk models trained on real labelled data — which a synthetic prototype cannot build.

## Attack classes NOT covered (the gateway does not stop these)

1. **Collusive merchant + agent** — if an *allowlisted* merchant is itself malicious and the agent is compromised, a correctly-priced purchase to an allowed merchant passes every rule. AgentGate assumes merchants on the allowlist are honest.
2. **Stolen mandate key** — the agent key is a bearer credential. If it leaks, an attacker inherits the full mandate. We hash keys at rest and scope them tightly, but we do not detect anomalous *use* of a valid key (no device binding, no behavioral baseline).
3. **Model-level jailbreaks** — the gateway does not care whether the agent's LLM was jailbroken, because the decision path has no LLM. But that also means the *system prompt* defense (line 1) can be fully defeated and we would not know; we rely entirely on line 2 (the gateway) holding. If an attack can be expressed as a rule-compliant purchase, no amount of gateway logic stops it.
4. **Timing/replay across the idempotency window** — idempotency and duplicate detection are windowed; a patient attacker operating outside the windows is not caught by those specific rules (though caps still apply).

## What production would require that this prototype lacks

- **Real fraud-data models** to replace fixed thresholds, cutting the false-positive rate by orders of magnitude while holding recall.
- **Agent identity infrastructure** — the emerging standards for authenticating an autonomous agent to a payment rail: NPCI's UAP, Google's Agent Payments Protocol (AP2), the Agentic Commerce Protocol (ACP). AgentGate's agent-key model is a stand-in for infrastructure that does not yet exist at standard.
- **Formal mandate infrastructure** — cryptographically-signed, revocable, delegatable spending mandates with regulatory backing (RBI e-mandate semantics), rather than a row in Postgres.
- **Liability and dispute handling** — who is responsible when an agent overspends is a legal question no code answers.

## What IS genuinely solid here

To be fair to the work: the deterministic decision path, the fail-closed behavior, the race-proof spend accounting, the hash-chained audit trail, and the mutation-tested rule suite are real, tested engineering. The gateway does what it claims — bound and gate every money action, explainably. The limitation is not correctness; it is that a bounded prototype cannot substitute for the data, standards, and infrastructure a production agentic-payments system needs.

---
*Regenerate the numbers in this document with `make eval`. Every eval run — including worse ones — is retained in the dashboard's Metrics history; we do not delete unflattering results.*
