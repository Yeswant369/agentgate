"""Money as integer paise. No floats, anywhere, ever.

A float cannot represent 0.1 rupees exactly; one float in a money path
compounds into paise-level drift that a reconciliation will catch and a
payments company will not forgive. All amounts are int paise + currency.
"""

from dataclasses import dataclass
from typing import Any

SUPPORTED_CURRENCIES = frozenset({"INR"})


class MoneyError(ValueError):
    pass


class CurrencyMismatch(MoneyError):
    pass


@dataclass(frozen=True, slots=True)
class Money:
    paise: int
    currency: str = "INR"

    def __post_init__(self) -> None:
        if isinstance(self.paise, bool) or not isinstance(self.paise, int):
            raise MoneyError(f"paise must be int, got {type(self.paise).__name__}")
        if self.paise < 0:
            raise MoneyError("negative amounts are modeled as refunds, not negative Money")
        if self.currency not in SUPPORTED_CURRENCIES:
            raise MoneyError(f"unsupported currency: {self.currency!r}")

    @classmethod
    def from_rupees(cls, rupees: int, paise: int = 0) -> "Money":
        """Build from whole rupees + optional paise part (both ints)."""
        if isinstance(rupees, bool) or not isinstance(rupees, int):
            raise MoneyError("rupees must be int")
        if not isinstance(paise, int) or paise < 0 or paise > 99:
            raise MoneyError("paise part must be an int in 0..99")
        return cls(rupees * 100 + paise)

    def _check(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            raise MoneyError(f"cannot combine Money with {type(other).__name__}")
        if other.currency != self.currency:
            raise CurrencyMismatch(f"{self.currency} vs {other.currency}")
        return other

    def __add__(self, other: "Money") -> "Money":
        return Money(self.paise + self._check(other).paise, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        other = self._check(other)
        if other.paise > self.paise:
            raise MoneyError("subtraction would go negative")
        return Money(self.paise - other.paise, self.currency)

    def percent_bp(self, basis_points: int) -> "Money":
        """A percentage expressed in basis points (1% == 100 bp), rounded
        half-up in integer arithmetic — deterministic, no float involved."""
        if not isinstance(basis_points, int) or basis_points < 0:
            raise MoneyError("basis_points must be a non-negative int")
        return Money((self.paise * basis_points + 5_000) // 10_000, self.currency)

    def __str__(self) -> str:
        return f"₹{self.paise // 100}.{self.paise % 100:02d}"
