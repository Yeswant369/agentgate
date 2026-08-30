from hypothesis import given
from hypothesis import strategies as st

from gateway.policy.rules import PolicyInput, evaluate


def make_input(**overrides) -> PolicyInput:
    base = dict(
        agent_id="agt_x",
        mandate_id="mdt_x",
        mandate_revoked=False,
        mandate_expired=False,
        merchant_allowlist=("m_voltedge",),
        allowed_categories=(),
        max_txn_paise=200_000,
        daily_cap_paise=500_000,
        merchant_id="m_voltedge",
        merchant_category="electronics",
        product_id="p_x",
        catalog_price_paise=50_000,
        claimed_price_paise=50_000,
        amount_paise=50_000,
        spent_today_paise=0,
        intents_in_velocity_window=0,
        duplicate_intents_in_window=0,
        merchant_spend_in_structuring_window_paise=0,
        merchant_txn_count_in_structuring_window=0,
    )
    base.update(overrides)
    return PolicyInput(**base)


def failed_rule_ids(decision):
    return {r.rule_id for r in decision.rule_results if r.outcome != "pass"}


def test_clean_purchase_allowed():
    d = evaluate(make_input())
    assert d.decision == "allow"


def test_revoked_and_expired_mandates_deny():
    assert evaluate(make_input(mandate_revoked=True)).decision == "deny"
    assert evaluate(make_input(mandate_expired=True)).decision == "deny"


def test_off_allowlist_merchant_denied_by_id():
    d = evaluate(make_input(merchant_id="m_lookalike_voltedge"))
    assert d.decision == "deny"
    assert "merchant_allowed" in failed_rule_ids(d)


def test_per_txn_cap_boundary_exact_cap_passes():
    assert (
        evaluate(
            make_input(
                amount_paise=200_000, claimed_price_paise=200_000, catalog_price_paise=200_000
            )
        ).decision
        != "deny"
    )
    d = evaluate(
        make_input(
            amount_paise=200_001, claimed_price_paise=200_001, catalog_price_paise=200_001
        )
    )
    assert "per_txn_cap" in failed_rule_ids(d)


def test_daily_cap_boundary():
    ok = evaluate(make_input(spent_today_paise=450_000))
    assert "daily_cap" not in failed_rule_ids(ok)  # 450k + 50k == cap exactly
    over = evaluate(make_input(spent_today_paise=450_001))
    assert "daily_cap" in failed_rule_ids(over)


def test_price_integrity_catches_injected_price():
    d = evaluate(make_input(claimed_price_paise=1_000))  # agent believes a lie
    assert d.decision == "deny"
    assert "price_integrity" in failed_rule_ids(d)


def test_structuring_sub_cap_transactions_summing_past_cap():
    d = evaluate(
        make_input(
            amount_paise=90_000,
            claimed_price_paise=90_000,
            catalog_price_paise=90_000,
            merchant_spend_in_structuring_window_paise=150_000,
            merchant_txn_count_in_structuring_window=2,
        )
    )
    assert d.decision == "deny"
    assert "structuring" in failed_rule_ids(d)


def test_near_cap_amount_requires_step_up():
    d = evaluate(
        make_input(
            amount_paise=180_000, claimed_price_paise=180_000, catalog_price_paise=180_000
        )
    )
    assert d.decision == "step_up"


def test_deny_beats_step_up():
    d = evaluate(
        make_input(
            amount_paise=180_000,
            claimed_price_paise=180_000,
            catalog_price_paise=180_000,
            mandate_revoked=True,
        )
    )
    assert d.decision == "deny"


# ---- property-based: the invariants example tests cannot exhaust ----

amounts = st.integers(min_value=1, max_value=200_000)


@given(st.lists(amounts, min_size=1, max_size=50))
def test_no_sequence_of_allowed_intents_can_exceed_daily_cap(seq):
    """THE core invariant: simulate any sequence of intents where spend
    accounting is applied exactly as the gateway applies it — the sum of
    allowed amounts never exceeds the daily cap."""
    daily_cap = 500_000
    spent = 0
    for amount in seq:
        d = evaluate(
            make_input(
                amount_paise=amount,
                claimed_price_paise=amount,
                catalog_price_paise=amount,
                spent_today_paise=spent,
                daily_cap_paise=daily_cap,
            )
        )
        if d.decision != "deny":
            spent += amount
    assert spent <= daily_cap


@given(amounts, st.integers(min_value=0, max_value=1_000_000))
def test_deny_by_default_is_total(amount, spent):
    """Every input produces exactly one decision and it is never an approval
    when any rule denied — no input can crash or bypass the pipeline."""
    d = evaluate(
        make_input(
            amount_paise=amount,
            claimed_price_paise=amount,
            catalog_price_paise=amount,
            spent_today_paise=spent,
        )
    )
    assert d.decision in {"allow", "deny", "step_up"}
    if any(r.outcome == "deny" for r in d.rule_results):
        assert d.decision == "deny"
