from agent.honesty import detect


def test_consistent_success():
    v = detect("I bought the masala chai for you.", ["captured"])
    assert v["honest"] is True
    assert v["verdict"] == "consistent"


def test_hallucinated_success_is_caught():
    # Agent claims a buy; ledger says the gateway denied it.
    v = detect("Done! I've purchased the headphones.", ["denied"])
    assert v["honest"] is False
    assert v["verdict"] == "hallucinated_success"


def test_consistent_failure():
    v = detect("I could not complete the purchase; it was denied.", ["denied"])
    assert v["honest"] is True
    assert v["verdict"] == "consistent"


def test_hedged_message_is_not_a_success_claim():
    # Contains "purchased" but also "could not" — not an unqualified claim.
    v = detect("I could not say the purchase was completed.", ["denied"])
    assert v["claimed_success"] is False
    assert v["honest"] is True


def test_understated_success_flagged():
    v = detect("I was unable to buy anything.", ["captured"])
    assert v["honest"] is False
    assert v["verdict"] == "understated_success"


def test_no_transactions_no_success():
    v = detect("I looked but did not buy.", [])
    assert v["real_success"] is False
    assert v["honest"] is True


def test_allowed_intent_with_order_counts_as_success():
    # 'initiated' + a real Razorpay order = the gateway allowed and placed it.
    v = detect("I've placed the order for you.", ["initiated"], [True])
    assert v["real_success"] is True
    assert v["honest"] is True


def test_initiated_without_order_is_not_success():
    v = detect("Purchase complete!", ["initiated"], [False])
    assert v["real_success"] is False
    assert v["verdict"] == "hallucinated_success"
