"""Eval regression suite — runs in CI, no DB or network.

This is the guard that makes the security rules un-rot-able: if a rule change
lets an attack through, or a mutation stops being caught, CI goes red.
"""

from evals.evaluate import classify
from evals.metrics import ConfusionMatrix, wilson
from evals.mutations import run_mutation_testing
from evals.run import run_replay
from evals.scenarios import all_scenarios


def test_scenario_set_is_balanced():
    scenarios = all_scenarios()
    legit = [s for s in scenarios if s.klass == "legit"]
    attacks = [s for s in scenarios if s.klass != "legit"]
    assert len(legit) == 40
    assert len(attacks) == 40
    assert len({s.klass for s in attacks}) >= 5


def test_no_attack_is_ever_missed():
    """The hard security guarantee: zero false negatives on the scenario set."""
    m = run_replay()
    assert m["confusion_matrix"]["fn"] == 0, "an attack slipped through"


def test_recall_is_total_on_scenarios():
    m = run_replay()
    assert m["confusion_matrix"]["recall"]["point"] == 1.0


def test_false_positives_are_known_and_stable():
    """We DO have false positives (honest edge cases). This pins the count so a
    rule change that blocks more good customers is caught as a regression."""
    m = run_replay()
    assert m["confusion_matrix"]["fp"] == 5


def test_every_mutation_is_caught():
    """If any weakened rule survives, the suite has a blind spot."""
    results = run_mutation_testing()
    surviving = [k for k, v in results.items() if not v["caught"]]
    assert surviving == [], f"mutations survived (blind spots): {surviving}"


def test_system_errors_are_not_counted_as_catches():
    cm = ConfusionMatrix()
    from evals.scenarios import Scenario
    from gateway.policy.rules import PolicyInput

    attack = Scenario(
        "x",
        "direct_overspend",
        "block",
        PolicyInput(
            agent_id="a",
            mandate_id="m",
            mandate_revoked=False,
            mandate_expired=False,
            merchant_allowlist=("m_x",),
            allowed_categories=(),
            max_txn_paise=1,
            daily_cap_paise=1,
            merchant_id="m_x",
            merchant_category="c",
            product_id="p",
            catalog_price_paise=100,
            claimed_price_paise=100,
            amount_paise=100,
            spent_today_paise=0,
            intents_in_velocity_window=0,
            duplicate_intents_in_window=0,
            merchant_spend_in_structuring_window_paise=0,
            merchant_txn_count_in_structuring_window=0,
        ),
    )
    assert classify(attack, "error", cm) == "error"
    assert cm.errors == 1
    assert cm.tp == 0  # a crash is not a catch


def test_wilson_interval_sane():
    p = wilson(40, 40)
    assert p.point == 1.0
    assert p.lo < 1.0 and p.hi == 1.0  # upper bound pinned, lower reflects n
    zero = wilson(0, 0)
    assert zero.point == 0.0 and zero.n == 0
