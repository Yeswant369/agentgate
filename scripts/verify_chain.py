#!/usr/bin/env python3
"""Independent audit-chain verifier — ZERO dependencies, stdlib only.

Do not trust AgentGate's /api/audit/verify endpoint. Fetch the exported chain
and check the hash arithmetic yourself:

    curl https://agentgate-ebon.vercel.app/api/audit/export > chain.json
    python3 scripts/verify_chain.py chain.json

This recomputes every hash from the genesis value using the documented
construction and reports the first break, if any. If it prints "CHAIN INTACT",
the audit log has not been tampered with since it was written — verified by
your machine, not ours.
"""

import hashlib
import json
import sys

GENESIS = "0" * 64
CONTENT_FIELDS = [
    "request_id",
    "agent_id",
    "mandate_id",
    "transaction_id",
    "decision",
    "policy_version",
    "input_snapshot",
    "rule_results",
]


def canonical(content: dict) -> str:
    return json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, content: dict) -> str:
    return hashlib.sha256((prev_hash + canonical(content)).encode()).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 verify_chain.py <chain.json>", file=sys.stderr)
        return 2
    with open(sys.argv[1]) as fh:
        data = json.load(fh)

    records = data["records"]
    prev_hash = GENESIS
    for rec in records:
        content = {k: rec[k] for k in CONTENT_FIELDS}
        if rec["prev_hash"] != prev_hash:
            print(f"CHAIN BROKEN at record {rec['id']}: prev_hash mismatch")
            print(f"  expected prev_hash: {prev_hash}")
            print(f"  stored   prev_hash: {rec['prev_hash']}")
            return 1
        expected = compute_hash(prev_hash, content)
        if rec["hash"] != expected:
            print(f"CHAIN BROKEN at record {rec['id']}: content hash mismatch")
            print(f"  recomputed: {expected}")
            print(f"  stored:     {rec['hash']}")
            return 1
        prev_hash = rec["hash"]

    print(f"CHAIN INTACT — {len(records)} records verified from genesis.")
    print(f"head hash: {prev_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
