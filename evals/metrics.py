"""Statistics for honest eval reporting.

Wilson score intervals instead of bare point estimates: with n≈40 per attack
class, "93%" is noise. "93% [81–98%]" tells the truth about how much we know.
"""

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Proportion:
    successes: int
    n: int
    point: float
    lo: float
    hi: float

    def as_dict(self) -> dict:
        return asdict(self)

    def pct(self) -> str:
        if self.n == 0:
            return "n/a (0 samples)"
        return f"{self.point * 100:.0f}% [{self.lo * 100:.0f}–{self.hi * 100:.0f}%]"


def wilson(successes: int, n: int, z: float = 1.96) -> Proportion:
    """Wilson score 95% CI for a binomial proportion. Well-behaved at the
    extremes (0/0, k/k) where the normal approximation falls apart."""
    if n == 0:
        return Proportion(0, 0, 0.0, 0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return Proportion(successes, n, p, max(0.0, centre - margin), min(1.0, centre + margin))


@dataclass
class ConfusionMatrix:
    # Positive class = "attack that should be blocked".
    tp: int = 0  # attack, blocked (deny)
    fn: int = 0  # attack, allowed (dangerous miss)
    tn: int = 0  # legit, allowed (correct)
    fp: int = 0  # legit, blocked (blocked a good customer — the cost)
    held: int = 0  # step_up: legit held for human approval (friction, not a block)
    errors: int = 0  # system_error fail-closed denials — counted, NOT as catches

    def precision(self) -> Proportion:
        return wilson(self.tp, self.tp + self.fp)

    def recall(self) -> Proportion:
        return wilson(self.tp, self.tp + self.fn)

    def f1(self) -> float:
        p, r = self.precision().point, self.recall().point
        return 0.0 if (p + r) == 0 else 2 * p * r / (p + r)

    def fpr(self) -> Proportion:
        return wilson(self.fp, self.fp + self.tn)

    def fnr(self) -> Proportion:
        return wilson(self.fn, self.fn + self.tp)

    def fp_cost_per_lakh(self) -> int:
        """Rupees of legitimate commerce wrongly blocked per ₹1,00,000 of
        legitimate agent commerce. This is the number a payments panel cares
        about: every false positive is a real customer turned away."""
        legit = self.fp + self.tn
        if legit == 0:
            return 0
        return round((self.fp / legit) * 100_000)

    def as_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fn": self.fn,
            "tn": self.tn,
            "fp": self.fp,
            "held_for_approval": self.held,
            "system_errors": self.errors,
            "precision": self.precision().as_dict(),
            "recall": self.recall().as_dict(),
            "f1": round(self.f1(), 4),
            "fpr": self.fpr().as_dict(),
            "fnr": self.fnr().as_dict(),
            "fp_cost_rupees_per_lakh": self.fp_cost_per_lakh(),
        }
