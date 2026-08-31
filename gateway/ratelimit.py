"""DB-backed fixed-window rate limiting.

On a stateless serverless gateway, an in-memory counter is a bug: it resets on
every cold start and is not shared across instances. The window lives in
Postgres, updated atomically under the row lock. The public playground being
bounded and gated is itself a demonstration of the product's thesis.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_and_increment(
    session: Session, bucket: str, client: str, limit: int, window_seconds: int
) -> tuple[bool, int]:
    """Returns (allowed, remaining). Atomic upsert: the window resets when the
    stored window_start is older than window_seconds, else the count increments.
    Enforced entirely in SQL so concurrent requests cannot race the limit."""
    row = session.execute(
        text(
            """
            INSERT INTO rate_limits (bucket, client, window_start, count)
            VALUES (:bucket, :client, now(), 1)
            ON CONFLICT (bucket, client) DO UPDATE SET
                window_start = CASE
                    WHEN rate_limits.window_start < now() - make_interval(secs => :win)
                    THEN now() ELSE rate_limits.window_start END,
                count = CASE
                    WHEN rate_limits.window_start < now() - make_interval(secs => :win)
                    THEN 1 ELSE rate_limits.count + 1 END
            RETURNING count
            """
        ),
        {"bucket": bucket, "client": client, "win": window_seconds},
    ).one()
    count = int(row[0])
    return (count <= limit, max(0, limit - count))
