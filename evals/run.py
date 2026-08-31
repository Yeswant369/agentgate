"""Run the eval suite, compute honest metrics, persist them, print a report.

Default mode is REPLAY (deterministic, free, no LLM): every scenario's
PolicyInput is evaluated by the real policy engine. This is the regression
suite CI runs. `--live` additionally drives the real Claude agent for a
sampled subset against the deployed gateway (Max-plan friendly).

Usage:
  python -m evals.run                 # replay, persist to DB
  python -m evals.run --no-persist    # replay, print only
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.evaluate import classify, per_class_detection  # noqa: E402
from evals.metrics import ConfusionMatrix  # noqa: E402
from evals.mutations import run_mutation_testing  # noqa: E402
from evals.scenarios import all_scenarios  # noqa: E402
from gateway.policy.rules import POLICY_VERSION, evaluate  # noqa: E402


def run_replay() -> dict:
    scenarios = all_scenarios()
    cm = ConfusionMatrix()
    per_scenario = []
    results = []
    for s in scenarios:
        decision = evaluate(s.policy_input, version=POLICY_VERSION).decision
        outcome = classify(s, decision, cm)
        results.append((s, outcome))
        per_scenario.append(
            {
                "id": s.id,
                "class": s.klass,
                "ground_truth": s.ground_truth,
                "decision": decision,
                "outcome": outcome,
            }
        )
    mutations = run_mutation_testing(scenarios)
    return {
        "mode": "replay",
        "policy_version": POLICY_VERSION,
        "scenario_count": len(scenarios),
        "confusion_matrix": cm.as_dict(),
        "per_class": per_class_detection(results),
        "mutation_testing": {
            "mutations_run": len(mutations),
            "all_caught": all(m["caught"] for m in mutations.values()),
            "surviving": [k for k, m in mutations.items() if not m["caught"]],
            "detail": mutations,
        },
        "per_scenario": per_scenario,
    }


def persist(metrics: dict, model: str | None) -> int | None:
    try:
        from gateway.db import get_session_factory
        from gateway.models import EvalRun
    except Exception:
        return None
    session = get_session_factory()()
    try:
        run = EvalRun(
            mode=metrics["mode"],
            model=model,
            scenario_count=metrics["scenario_count"],
            metrics=metrics,
        )
        session.add(run)
        session.commit()
        return run.id
    except Exception as exc:  # pragma: no cover - persistence is best-effort
        session.rollback()
        print(f"warning: could not persist eval run: {exc}", file=sys.stderr)
        return None
    finally:
        session.close()


def print_report(m: dict) -> None:
    cm = m["confusion_matrix"]
    print(f"\n=== AgentGate eval — {m['mode']} mode, {m['scenario_count']} scenarios ===\n")
    print("Confusion matrix (positive class = attack that should be blocked):")
    print(f"  TP (attack blocked):   {cm['tp']}")
    print(f"  FN (attack MISSED):    {cm['fn']}")
    print(f"  TN (legit allowed):    {cm['tn']}")
    print(f"  FP (legit BLOCKED):    {cm['fp']}")
    print(f"  held for approval:     {cm['held_for_approval']}")
    print(f"  system errors:         {cm['system_errors']}  (not counted as catches)")
    print(f"\n  precision: {_p(cm['precision'])}")
    print(f"  recall:    {_p(cm['recall'])}")
    print(f"  F1:        {cm['f1']:.3f}")
    print(f"  FPR:       {_p(cm['fpr'])}")
    print(f"  FNR:       {_p(cm['fnr'])}")
    print(
        f"\n  FALSE-POSITIVE COST: ~₹{cm['fp_cost_rupees_per_lakh']:,} of legitimate "
        f"commerce blocked per ₹1,00,000 of legitimate agent commerce."
    )
    print("\nPer-attack-class detection (Wilson 95% CI):")
    for klass, r in m["per_class"].items():
        if klass == "legit":
            print(
                f"  {klass:26s} n={r['n']:2d}  correct-allow {_p(r['correct_allow'])}  "
                f"FP={r['false_positives']} held={r['held_for_approval']}"
            )
        else:
            print(
                f"  {klass:26s} n={r['n']:2d}  detection {_p(r['detection'])}  "
                f"missed={r['missed']}"
            )
    mt = m["mutation_testing"]
    status = "ALL CAUGHT ✓" if mt["all_caught"] else f"SURVIVING: {mt['surviving']}"
    print(f"\nMutation testing: {mt['mutations_run']} mutations — {status}")


def _p(d: dict) -> str:
    if d["n"] == 0:
        return "n/a"
    return f"{d['point'] * 100:.0f}% [{d['lo'] * 100:.0f}–{d['hi'] * 100:.0f}%]"


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentGate eval harness")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--json", action="store_true", help="dump raw metrics JSON")
    args = parser.parse_args()

    metrics = run_replay()
    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print_report(metrics)
    if not args.no_persist:
        run_id = persist(metrics, model=None)
        if run_id:
            print(f"\npersisted as eval_run #{run_id}")

    # Non-zero exit if any mutation survived — this is the CI gate.
    sys.exit(0 if metrics["mutation_testing"]["all_caught"] else 1)


if __name__ == "__main__":
    main()
