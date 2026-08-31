"""CLI: run the buyer agent against the deployed (or local) gateway.

Usage:
  python -m agent.run --key agk_xxx "buy a masala chai blend under 500 rupees"
  python -m agent.run --key agk_xxx --scenario legit_chai "..."

Reports the agent's claims, the ledger truth, and the honesty verdict, then
records the full transcript to the gateway for the Phase 5 evals and Phase 6
replay playground.
"""

import argparse
import sys

from agent.buyer_agent import run_agent_sync
from agent.gateway_client import GatewayClient
from agent.honesty import detect


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentGate buyer agent")
    parser.add_argument("intent", help="natural-language shopping intent")
    parser.add_argument("--key", required=True, help="agent API key (agk_...)")
    parser.add_argument("--scenario", default=None, help="scenario label for evals")
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--url", default=None, help="gateway base URL override")
    args = parser.parse_args()

    gw = GatewayClient(args.key, base_url=args.url) if args.url else GatewayClient(args.key)

    print(f"intent: {args.intent}\n")
    result = run_agent_sync(args.intent, gw, model=args.model)

    print("agent tool calls:")
    for call in result.tool_calls:
        extra = f" -> {call.get('decision')}" if call.get("decision") else ""
        print(f"  {call['tool']}({call['args']}){extra}")

    # Ledger truth for every transaction the agent created.
    ledger_states = []
    has_order = []
    for txn_id in result.transaction_ids:
        status = gw.check_intent_status(txn_id)
        ledger_states.append(status.get("state", "unknown"))
        has_order.append(bool(status.get("razorpay_order_id")))
    honesty = detect(result.final_text, ledger_states, has_order)

    print(f"\nagent's final claim:\n  {result.final_text[:400]}")
    print(f"\nledger truth: {ledger_states}")
    print(f"honesty verdict: {honesty['verdict']} (honest={honesty['honest']})")

    session = gw.record_session(
        {
            "intent": args.intent,
            "scenario": args.scenario,
            "transcript": result.transcript,
            "claimed": {
                "final_text": result.final_text,
                "claimed_success": honesty["claimed_success"],
            },
            "actual": {
                "ledger_states": ledger_states,
                "transaction_ids": result.transaction_ids,
            },
            "honest": honesty["honest"],
        }
    )
    print(f"\ntranscript recorded: {session['session_id']}")
    sys.exit(0 if honesty["honest"] else 2)


if __name__ == "__main__":
    main()
