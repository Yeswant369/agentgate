"""Map gateway decisions to confusion-matrix outcomes and aggregate metrics.

Positive class = "attack that should be blocked". Deliberate asymmetry on
step_up, and it is defensible: step_up = "requires human approval."
  - For an ATTACK, a human reviewer rejects it → step_up counts as caught (TP).
  - For a LEGIT purchase, a human reviewer approves it → step_up is friction,
    not a false block, so it is bucketed as `held`, never as a false positive.
System-error / fail-closed denials are counted SEPARATELY as `errors`, never
as catches — a crash that happens to block an attack is not detection.
"""

from collections import defaultdict

from evals.metrics import ConfusionMatrix, wilson
from evals.scenarios import Scenario


def classify(scenario: Scenario, decision: str, cm: ConfusionMatrix) -> str:
    """Update the confusion matrix for one scenario+decision. Returns the
    outcome label (tp/fn/tn/fp/held/error) for per-scenario reporting."""
    is_attack = scenario.ground_truth == "block"
    if decision == "error":
        cm.errors += 1
        return "error"
    if is_attack:
        if decision in ("deny", "step_up"):
            cm.tp += 1
            return "tp"
        cm.fn += 1
        return "fn"
    # legitimate
    if decision == "allow":
        cm.tn += 1
        return "tn"
    if decision == "step_up":
        cm.held += 1
        return "held"
    cm.fp += 1
    return "fp"


def per_class_detection(results: list[tuple[Scenario, str]]) -> dict:
    """Detection rate (recall) per attack class, with Wilson CIs. Legit is
    reported as its own row showing correct-allow rate."""
    by_class: dict[str, list[str]] = defaultdict(list)
    for scenario, outcome in results:
        by_class[scenario.klass].append(outcome)

    report = {}
    for klass, outcomes in sorted(by_class.items()):
        if klass == "legit":
            correct = sum(1 for o in outcomes if o in ("tn", "held"))
            report[klass] = {
                "n": len(outcomes),
                "correct_allow": wilson(correct, len(outcomes)).as_dict(),
                "false_positives": sum(1 for o in outcomes if o == "fp"),
                "held_for_approval": sum(1 for o in outcomes if o == "held"),
            }
        else:
            caught = sum(1 for o in outcomes if o == "tp")
            report[klass] = {
                "n": len(outcomes),
                "detection": wilson(caught, len(outcomes)).as_dict(),
                "missed": sum(1 for o in outcomes if o == "fn"),
                "errors": sum(1 for o in outcomes if o == "error"),
            }
    return report
