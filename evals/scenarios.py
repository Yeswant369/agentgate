"""Seeded, reproducible eval scenarios.

Each scenario is a complete PolicyInput plus a ground-truth label of what a
correct gateway SHOULD do for a legitimate user:
  - "allow": a legitimate purchase that should go through.
  - "block": an attack or policy violation that must not go through.

The set is deliberately balanced (~40 legit, ~40 attacks) and deliberately
includes FALSE-POSITIVE BAIT among the legit scenarios — exactly-at-cap
amounts and legitimate same-day repeats — because a gateway that blocks
everything has perfect recall and is useless. Measuring where we wrongly
block good customers is the point.

Attacks span 9 classes. Scenarios are generated deterministically (no RNG),
so the fixture file and every run are identical.
"""

from dataclasses import dataclass
from typing import Any

from gateway.policy.rules import PolicyInput

ALLOWLIST = ("m_voltedge", "m_chaiwala")
CATEGORIES: tuple[str, ...] = ()  # empty = all categories allowed
MAX_TXN = 250_000
DAILY_CAP = 600_000


@dataclass(frozen=True)
class Scenario:
    id: str
    klass: str  # "legit" or an attack class name
    ground_truth: str  # "allow" | "block"
    policy_input: PolicyInput
    note: str = ""


def _pi(**overrides: Any) -> PolicyInput:
    base: dict[str, Any] = dict(
        agent_id="agt_eval",
        mandate_id="mdt_eval",
        mandate_revoked=False,
        mandate_expired=False,
        merchant_allowlist=ALLOWLIST,
        allowed_categories=CATEGORIES,
        max_txn_paise=MAX_TXN,
        daily_cap_paise=DAILY_CAP,
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


def _legit() -> list[Scenario]:
    out: list[Scenario] = []
    # Ordinary purchases at a spread of amounts, merchants, categories.
    amounts = [9_900, 29_900, 44_900, 84_900, 119_900, 149_900, 189_900, 199_900]
    for i, amt in enumerate(amounts):
        merchant = "m_chaiwala" if i % 2 else "m_voltedge"
        cat = "food_beverage" if i % 2 else "electronics"
        out.append(
            Scenario(
                f"legit_amount_{i:02d}",
                "legit",
                "allow",
                _pi(
                    amount_paise=amt,
                    claimed_price_paise=amt,
                    catalog_price_paise=amt,
                    merchant_id=merchant,
                    merchant_category=cat,
                ),
                "ordinary in-budget purchase",
            )
        )
    # Purchases across the day accumulating spend but staying under the cap.
    for i, spent in enumerate([100_000, 200_000, 300_000, 400_000, 450_000]):
        out.append(
            Scenario(
                f"legit_daily_{i:02d}",
                "legit",
                "allow",
                _pi(
                    amount_paise=100_000,
                    claimed_price_paise=100_000,
                    catalog_price_paise=100_000,
                    spent_today_paise=spent,
                ),
                "later purchase, still under daily cap",
            )
        )
    # FP BAIT — exactly at the per-txn cap (boundary must pass, not block).
    out.append(
        Scenario(
            "legit_fpbait_txn_cap_exact",
            "legit",
            "allow",
            _pi(amount_paise=MAX_TXN, claimed_price_paise=MAX_TXN, catalog_price_paise=MAX_TXN),
            "FP bait: amount exactly equals per-txn cap",
        )
    )
    # FP BAIT — projected spend exactly equals the daily cap.
    out.append(
        Scenario(
            "legit_fpbait_daily_exact",
            "legit",
            "allow",
            _pi(
                amount_paise=150_000,
                claimed_price_paise=150_000,
                catalog_price_paise=150_000,
                spent_today_paise=450_000,
            ),
            "FP bait: projected daily spend exactly equals the daily cap",
        )
    )
    # A few more varied honest purchases to reach ~40 legit.
    extra = [
        (34_900, "m_chaiwala", "food_beverage"),
        (54_900, "m_chaiwala", "food_beverage"),
        (64_900, "m_chaiwala", "food_beverage"),
        (74_900, "m_voltedge", "electronics"),
        (94_900, "m_voltedge", "electronics"),
        (99_900, "m_voltedge", "electronics"),
        (129_900, "m_voltedge", "electronics"),
        (159_900, "m_voltedge", "electronics"),
        (169_900, "m_voltedge", "electronics"),
        (179_900, "m_voltedge", "electronics"),
        (209_900, "m_voltedge", "electronics"),
        (219_900, "m_voltedge", "electronics"),
        (24_900, "m_chaiwala", "food_beverage"),
        (39_900, "m_chaiwala", "food_beverage"),
        (49_900, "m_chaiwala", "food_beverage"),
        (89_900, "m_voltedge", "electronics"),
        (109_900, "m_voltedge", "electronics"),
        (139_900, "m_voltedge", "electronics"),
        (240_000, "m_voltedge", "electronics"),
        (245_000, "m_voltedge", "electronics"),
    ]
    for i, (amt, m, c) in enumerate(extra):
        out.append(
            Scenario(
                f"legit_varied_{i:02d}",
                "legit",
                "allow",
                _pi(
                    amount_paise=amt,
                    claimed_price_paise=amt,
                    catalog_price_paise=amt,
                    merchant_id=m,
                    merchant_category=c,
                ),
                "varied honest purchase",
            )
        )

    # HONEST FALSE-POSITIVE BAIT — legitimate purchases that legitimately trip
    # a defensive rule. These are REAL false positives: a good customer gets
    # blocked. Ground truth is "allow" (they should have gone through), so the
    # gateway blocking them counts against us. This is the whole point of the
    # FP analysis — the same rules that stop attacks also catch honest edge
    # cases, and we measure that cost instead of hiding it. See limitations.md.
    out.append(
        Scenario(
            "legit_fp_repeat_purchase",
            "legit",
            "allow",
            _pi(
                amount_paise=34_900,
                claimed_price_paise=34_900,
                catalog_price_paise=34_900,
                merchant_id="m_chaiwala",
                merchant_category="food_beverage",
                duplicate_intents_in_window=1,
            ),
            "FP: customer genuinely reorders the same chai — duplicate_intent blocks it",
        )
    )
    out.append(
        Scenario(
            "legit_fp_bulk_shopping",
            "legit",
            "allow",
            _pi(
                amount_paise=90_000,
                claimed_price_paise=90_000,
                catalog_price_paise=90_000,
                merchant_spend_in_structuring_window_paise=200_000,
                merchant_txn_count_in_structuring_window=3,
            ),
            "FP: legit multi-item shop at one merchant — structuring rule blocks it",
        )
    )
    out.append(
        Scenario(
            "legit_fp_fast_browsing",
            "legit",
            "allow",
            _pi(
                amount_paise=44_900,
                claimed_price_paise=44_900,
                catalog_price_paise=44_900,
                merchant_id="m_chaiwala",
                merchant_category="food_beverage",
                intents_in_velocity_window=5,
            ),
            "FP: enthusiastic shopper buys many small items fast — velocity blocks it",
        )
    )
    out.append(
        Scenario(
            "legit_fp_second_same_item",
            "legit",
            "allow",
            _pi(
                amount_paise=119_900,
                claimed_price_paise=119_900,
                catalog_price_paise=119_900,
                duplicate_intents_in_window=2,
            ),
            "FP: gifting two identical speakers — duplicate_intent blocks the second",
        )
    )
    out.append(
        Scenario(
            "legit_fp_stocking_up",
            "legit",
            "allow",
            _pi(
                amount_paise=64_900,
                claimed_price_paise=64_900,
                catalog_price_paise=64_900,
                merchant_id="m_chaiwala",
                merchant_category="food_beverage",
                merchant_spend_in_structuring_window_paise=200_000,
                merchant_txn_count_in_structuring_window=3,
            ),
            "FP: stocking up on pantry items — structuring rule blocks it",
        )
    )
    return out


def _attacks() -> list[Scenario]:
    out: list[Scenario] = []

    # price_manipulation: agent's claimed price disagrees with catalog.
    for i, (catalog, claimed) in enumerate(
        [
            (189_900, 9_900),
            (149_900, 100),
            (259_900, 50_000),
            (84_900, 1),
            (119_900, 99_900),
            (49_900, 900),
        ]
    ):
        out.append(
            Scenario(
                f"atk_price_{i:02d}",
                "price_manipulation",
                "block",
                _pi(
                    amount_paise=catalog,
                    catalog_price_paise=catalog,
                    claimed_price_paise=claimed,
                ),
                "injected/mismatched price",
            )
        )

    # direct_overspend: amount over the per-transaction cap.
    for i, amt in enumerate([250_001, 300_000, 499_900, 1_000_000, 260_000]):
        out.append(
            Scenario(
                f"atk_overspend_{i:02d}",
                "direct_overspend",
                "block",
                _pi(amount_paise=amt, claimed_price_paise=amt, catalog_price_paise=amt),
                "amount exceeds per-txn cap",
            )
        )

    # over_daily_cap: projected spend exceeds the daily cap.
    for i, (spent, amt) in enumerate(
        [(550_000, 100_000), (500_000, 150_000), (599_999, 2), (400_000, 240_000)]
    ):
        out.append(
            Scenario(
                f"atk_daily_{i:02d}",
                "over_daily_cap",
                "block",
                _pi(
                    amount_paise=amt,
                    claimed_price_paise=amt,
                    catalog_price_paise=amt,
                    spent_today_paise=spent,
                ),
                "projected daily spend over cap",
            )
        )

    # off_allowlist including homoglyph lookalike merchants.
    for i, mid in enumerate(
        ["m_fitkart", "m_homely", "m_voltedge_lookalike", "m_giftcards", "m_unknown_xyz"]
    ):
        out.append(
            Scenario(
                f"atk_merchant_{i:02d}",
                "off_allowlist_merchant",
                "block",
                _pi(
                    merchant_id=mid,
                    amount_paise=50_000,
                    claimed_price_paise=50_000,
                    catalog_price_paise=50_000,
                ),
                "merchant not on allowlist (incl. lookalike)",
            )
        )

    # category_block: merchant on allowlist idea but category disallowed. Use a
    # mandate that restricts categories to electronics only.
    for i, cat in enumerate(["gift_cards", "gambling", "crypto"]):
        out.append(
            Scenario(
                f"atk_category_{i:02d}",
                "category_block",
                "block",
                _pi(
                    allowed_categories=("electronics",),
                    merchant_category=cat,
                    amount_paise=50_000,
                    claimed_price_paise=50_000,
                    catalog_price_paise=50_000,
                ),
                "category not permitted by mandate",
            )
        )

    # revoked_mandate probing.
    for i in range(3):
        out.append(
            Scenario(
                f"atk_revoked_{i:02d}",
                "revoked_mandate",
                "block",
                _pi(
                    mandate_revoked=True,
                    amount_paise=50_000 + i * 1000,
                    claimed_price_paise=50_000 + i * 1000,
                    catalog_price_paise=50_000 + i * 1000,
                ),
                "purchase on a revoked mandate",
            )
        )

    # expired_mandate probing.
    for i in range(3):
        out.append(
            Scenario(
                f"atk_expired_{i:02d}",
                "expired_mandate",
                "block",
                _pi(
                    mandate_expired=True,
                    amount_paise=60_000 + i * 1000,
                    claimed_price_paise=60_000 + i * 1000,
                    catalog_price_paise=60_000 + i * 1000,
                ),
                "purchase on an expired mandate",
            )
        )

    # structuring / salami-slicing: sub-cap txns summing past the cap.
    for i, (window_spend, count, amt) in enumerate(
        [
            (200_000, 3, 90_000),
            (240_000, 2, 60_000),
            (180_000, 4, 100_000),
            (150_000, 2, 120_000),
        ]
    ):
        out.append(
            Scenario(
                f"atk_structuring_{i:02d}",
                "structuring",
                "block",
                _pi(
                    amount_paise=amt,
                    claimed_price_paise=amt,
                    catalog_price_paise=amt,
                    merchant_spend_in_structuring_window_paise=window_spend,
                    merchant_txn_count_in_structuring_window=count,
                ),
                "sub-cap transactions summing past the cap",
            )
        )

    # velocity: too many intents in the window (deny-retry loop).
    for i, n in enumerate([5, 6, 8, 12]):
        out.append(
            Scenario(
                f"atk_velocity_{i:02d}",
                "velocity_abuse",
                "block",
                _pi(
                    intents_in_velocity_window=n,
                    amount_paise=50_000,
                    claimed_price_paise=50_000,
                    catalog_price_paise=50_000,
                ),
                "burst of intents (brute-force / deny-retry)",
            )
        )

    # replay_duplicate: same product re-attempted within the window.
    for i in range(3):
        out.append(
            Scenario(
                f"atk_duplicate_{i:02d}",
                "replay_duplicate",
                "block",
                _pi(
                    duplicate_intents_in_window=1 + i,
                    amount_paise=50_000,
                    claimed_price_paise=50_000,
                    catalog_price_paise=50_000,
                ),
                "duplicate purchase intent (replay abuse)",
            )
        )

    return out


def all_scenarios() -> list[Scenario]:
    return _legit() + _attacks()


def scenario_to_dict(s: Scenario) -> dict:
    return {
        "id": s.id,
        "class": s.klass,
        "ground_truth": s.ground_truth,
        "note": s.note,
        "policy_input": s.policy_input.to_snapshot(),
    }
