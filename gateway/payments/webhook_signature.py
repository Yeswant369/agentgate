"""Razorpay webhook signature verification.

Pure function, deliberately isolated: it is unit-tested against forged and
tampered payloads without any HTTP or DB involvement.
"""

import hashlib
import hmac


def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """HMAC-SHA256 over the raw request body, compared in constant time.
    A naive == comparison leaks timing information; compare_digest does not."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
