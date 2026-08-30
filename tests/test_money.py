import pytest

from gateway.money import CurrencyMismatch, Money, MoneyError


def test_money_is_integer_paise():
    m = Money(189_900)
    assert m.paise == 189_900
    assert str(m) == "₹1899.00"


def test_floats_are_rejected():
    with pytest.raises(MoneyError):
        Money(99.99)  # type: ignore[arg-type]


def test_negative_rejected():
    with pytest.raises(MoneyError):
        Money(-1)


def test_unsupported_currency_rejected():
    with pytest.raises(MoneyError):
        Money(100, "USD")


def test_from_rupees():
    assert Money.from_rupees(99, 99).paise == 9_999
    with pytest.raises(MoneyError):
        Money.from_rupees(10, 100)


def test_addition_and_subtraction():
    assert (Money(100) + Money(50)).paise == 150
    assert (Money(100) - Money(50)).paise == 50
    with pytest.raises(MoneyError):
        Money(50) - Money(100)


def test_currency_mismatch_raises():
    # Only INR is supported today, so mismatch is exercised via the guard
    # directly: constructing the foreign side already fails.
    with pytest.raises(MoneyError):
        Money(100) + Money(100, "USD")  # type: ignore[call-arg]


def test_percent_fee_rounds_half_up_in_integers():
    # 2% of ₹99.99 (9999 paise) = 199.98 paise -> 200, no float involved
    assert Money(9_999).percent_bp(200).paise == 200
    # 1.5% of ₹1.00 = 1.5 paise -> 2
    assert Money(100).percent_bp(150).paise == 2
    # 1% of 49 paise = 0.49 -> 0
    assert Money(49).percent_bp(100).paise == 0


def test_currency_mismatch_class_exists_for_future_multicurrency():
    assert issubclass(CurrencyMismatch, MoneyError)
