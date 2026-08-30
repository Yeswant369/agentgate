"""The policy ruleset: pure, deterministic functions over a frozen input.

There is deliberately NO LLM anywhere in this module or anything it imports.
When the panel asks "what if the model misbehaves?", the answer is: the
decision path has no model in it. Every rule returns a machine-readable
verdict with human-readable reasoning and the evidence it used.

Rules are versioned: a decision records the policy_version that produced it,
and the replay endpoint re-runs that exact version. Changing ANY rule
behavior requires adding a new version, never editing an old one.
"""

from dataclasses import dataclass, field
from typing import Literal

Outcome = Literal["pass", "deny", "step_up"]

# Windows and limits for v1. Constants, not config: changing them is a policy
# change and must bump POLICY_VERSION.
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_MAX_INTENTS = 5
DUPLICATE_WINDOW_MINUTES = 2
STRUCTURING_WINDOW_MINUTES = 60
STEP_UP_FRACTION_BP = 8_000  # >= 80% of per-txn cap requires human approval


@dataclass(frozen=True)
class PolicyInput:
    """Everything a ruleset may consider, gathered up front so rules stay
    pure. Serialized verbatim into the audit record for deterministic replay."""

    agent_id: str
    mandate_id: str
    mandate_revoked: bool
    mandate_expired: bool  # computed against DB time by the gatherer
    merchant_allowlist: tuple[str, ...]
    allowed_categories: tuple[str, ...]
    max_txn_paise: int
    daily_cap_paise: int
    merchant_id: str
    merchant_category: str
    product_id: str
    catalog_price_paise: int
    claimed_price_paise: int  # what the agent believes it should pay
    amount_paise: int  # what would actually be charged (catalog price)
    spent_today_paise: int  # committed + reserved, gathered under row lock
    intents_in_velocity_window: int
    duplicate_intents_in_window: int
    merchant_spend_in_structuring_window_paise: int
    merchant_txn_count_in_structuring_window: int

    def to_snapshot(self) -> dict:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}

    @classmethod
    def from_snapshot(cls, snap: dict) -> "PolicyInput":
        data = dict(snap)
        data["merchant_allowlist"] = tuple(data.get("merchant_allowlist", ()))
        data["allowed_categories"] = tuple(data.get("allowed_categories", ()))
        return cls(**data)


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    outcome: Outcome
    reason: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "outcome": self.outcome,
            "reason": self.reason,
            "evidence": self.evidence,
        }


def _mandate_active(i: PolicyInput) -> RuleResult:
    if i.mandate_revoked:
        return RuleResult("mandate_active", "deny", "mandate has been revoked")
    if i.mandate_expired:
        return RuleResult("mandate_active", "deny", "mandate has expired")
    return RuleResult("mandate_active", "pass", "mandate is active and unexpired")


def _merchant_allowed(i: PolicyInput) -> RuleResult:
    if i.merchant_id in i.merchant_allowlist:
        return RuleResult(
            "merchant_allowed",
            "pass",
            "merchant is on the mandate allowlist",
            {"merchant_id": i.merchant_id},
        )
    return RuleResult(
        "merchant_allowed",
        "deny",
        "merchant is not on the mandate allowlist (matched by ID, never by name)",
        {"merchant_id": i.merchant_id, "allowlist_size": len(i.merchant_allowlist)},
    )


def _category_allowed(i: PolicyInput) -> RuleResult:
    if not i.allowed_categories or i.merchant_category in i.allowed_categories:
        return RuleResult(
            "category_allowed",
            "pass",
            "category permitted by mandate",
            {"category": i.merchant_category},
        )
    return RuleResult(
        "category_allowed",
        "deny",
        "category is not permitted by this mandate",
        {"category": i.merchant_category, "allowed": list(i.allowed_categories)},
    )


def _per_txn_cap(i: PolicyInput) -> RuleResult:
    if i.amount_paise <= i.max_txn_paise:
        return RuleResult(
            "per_txn_cap",
            "pass",
            "amount within per-transaction cap",
            {"amount_paise": i.amount_paise, "cap_paise": i.max_txn_paise},
        )
    return RuleResult(
        "per_txn_cap",
        "deny",
        "amount exceeds the per-transaction cap",
        {"amount_paise": i.amount_paise, "cap_paise": i.max_txn_paise},
    )


def _daily_cap(i: PolicyInput) -> RuleResult:
    projected = i.spent_today_paise + i.amount_paise
    if projected <= i.daily_cap_paise:
        return RuleResult(
            "daily_cap",
            "pass",
            "projected daily spend within cap",
            {
                "spent_today_paise": i.spent_today_paise,
                "projected_paise": projected,
                "cap_paise": i.daily_cap_paise,
            },
        )
    return RuleResult(
        "daily_cap",
        "deny",
        "projected daily spend would exceed the daily cap",
        {
            "spent_today_paise": i.spent_today_paise,
            "projected_paise": projected,
            "cap_paise": i.daily_cap_paise,
        },
    )


def _price_integrity(i: PolicyInput) -> RuleResult:
    if i.claimed_price_paise == i.catalog_price_paise:
        return RuleResult(
            "price_integrity",
            "pass",
            "agent's claimed price matches the catalog",
            {"catalog_paise": i.catalog_price_paise},
        )
    return RuleResult(
        "price_integrity",
        "deny",
        "agent's claimed price disagrees with the catalog — possible listing "
        "manipulation or price-injection",
        {"claimed_paise": i.claimed_price_paise, "catalog_paise": i.catalog_price_paise},
    )


def _velocity(i: PolicyInput) -> RuleResult:
    if i.intents_in_velocity_window < VELOCITY_MAX_INTENTS:
        return RuleResult(
            "velocity",
            "pass",
            "intent rate within limits",
            {
                "intents_in_window": i.intents_in_velocity_window,
                "window_minutes": VELOCITY_WINDOW_MINUTES,
            },
        )
    return RuleResult(
        "velocity",
        "deny",
        "too many purchase intents in the window (includes denied attempts — "
        "a deny-retry loop trips this)",
        {
            "intents_in_window": i.intents_in_velocity_window,
            "max": VELOCITY_MAX_INTENTS,
            "window_minutes": VELOCITY_WINDOW_MINUTES,
        },
    )


def _duplicate_intent(i: PolicyInput) -> RuleResult:
    if i.duplicate_intents_in_window == 0:
        return RuleResult("duplicate_intent", "pass", "no near-duplicate intent in window")
    return RuleResult(
        "duplicate_intent",
        "deny",
        "an allowed intent for the same product exists within the duplicate "
        "window under a different idempotency key",
        {
            "duplicates": i.duplicate_intents_in_window,
            "window_minutes": DUPLICATE_WINDOW_MINUTES,
        },
    )


def _structuring(i: PolicyInput) -> RuleResult:
    projected = i.merchant_spend_in_structuring_window_paise + i.amount_paise
    if i.merchant_txn_count_in_structuring_window >= 2 and projected > i.max_txn_paise:
        return RuleResult(
            "structuring",
            "deny",
            "multiple sub-cap transactions to one merchant sum past the "
            "per-transaction cap — salami-slicing pattern",
            {
                "window_spend_paise": i.merchant_spend_in_structuring_window_paise,
                "window_count": i.merchant_txn_count_in_structuring_window,
                "projected_paise": projected,
                "cap_paise": i.max_txn_paise,
                "window_minutes": STRUCTURING_WINDOW_MINUTES,
            },
        )
    return RuleResult(
        "structuring",
        "pass",
        "no structuring pattern at this merchant",
        {
            "window_spend_paise": i.merchant_spend_in_structuring_window_paise,
            "window_count": i.merchant_txn_count_in_structuring_window,
        },
    )


def _step_up_near_cap(i: PolicyInput) -> RuleResult:
    threshold = (i.max_txn_paise * STEP_UP_FRACTION_BP) // 10_000
    if i.amount_paise >= threshold:
        return RuleResult(
            "step_up_near_cap",
            "step_up",
            "amount is near the per-transaction cap; human approval required",
            {"amount_paise": i.amount_paise, "threshold_paise": threshold},
        )
    return RuleResult(
        "step_up_near_cap",
        "pass",
        "amount well under the step-up threshold",
        {"threshold_paise": threshold},
    )


RULESET_V1 = [
    _mandate_active,
    _merchant_allowed,
    _category_allowed,
    _per_txn_cap,
    _daily_cap,
    _price_integrity,
    _velocity,
    _duplicate_intent,
    _structuring,
    _step_up_near_cap,
]

RULESETS = {1: RULESET_V1}
POLICY_VERSION = 1


@dataclass(frozen=True)
class Decision:
    decision: Literal["allow", "deny", "step_up"]
    policy_version: int
    rule_results: list[RuleResult]

    def to_rule_dicts(self) -> list[dict]:
        return [r.to_dict() for r in self.rule_results]


def evaluate(policy_input: PolicyInput, version: int = POLICY_VERSION) -> Decision:
    """Deny-by-default: every rule runs (full evidence in the audit record),
    any deny wins, else any step_up wins, else allow."""
    results = [rule(policy_input) for rule in RULESETS[version]]
    decision: Literal["allow", "deny", "step_up"]
    if any(r.outcome == "deny" for r in results):
        decision = "deny"
    elif any(r.outcome == "step_up" for r in results):
        decision = "step_up"
    else:
        decision = "allow"
    return Decision(decision=decision, policy_version=version, rule_results=results)
