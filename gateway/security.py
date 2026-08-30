import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException

from gateway.config import get_settings


def generate_agent_key() -> tuple[str, str]:
    """Returns (plaintext_key, sha256_hash). The plaintext is shown exactly
    once at creation; only the hash is ever stored."""
    key = f"agk_{secrets.token_urlsafe(32)}"
    return key, hash_agent_key(key)


def hash_agent_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def require_admin(x_admin_token: str = Header(default="")) -> None:
    """Admin surface guard: single operator token, constant-time compare.
    Unconfigured token means the surface is OFF — fail closed, not open."""
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(status_code=503, detail="admin surface is not configured")
    if not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="invalid admin token")
