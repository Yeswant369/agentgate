"""Run reconciliation against Razorpay test mode and print the report."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway.db import get_session_factory  # noqa: E402
from gateway.recon import run_reconciliation  # noqa: E402


def main() -> None:
    session = get_session_factory()()
    try:
        report = run_reconciliation(session)
    finally:
        session.close()
    print("reconciliation report")
    print(f"  matched:        {report.matched}")
    print(f"  mismatched:     {report.mismatched}")
    print(f"  missing_local:  {report.missing_local}")
    print(f"  missing_remote: {report.missing_remote}")
    for item in report.details[:20]:
        print(f"  ! {item}")
    if report.mismatched or report.missing_local:
        sys.exit(1)


if __name__ == "__main__":
    main()
