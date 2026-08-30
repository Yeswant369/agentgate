import hashlib
import hmac

from gateway.payments.webhook_signature import verify_webhook_signature

SECRET = "whsec_test_secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_accepted():
    body = b'{"event":"payment.captured"}'
    assert verify_webhook_signature(body, sign(body), SECRET) is True


def test_wrong_secret_rejected():
    body = b'{"event":"payment.captured"}'
    assert verify_webhook_signature(body, sign(body, "other_secret"), SECRET) is False


def test_tampered_body_rejected():
    body = b'{"event":"payment.captured","amount":10000}'
    signature = sign(body)
    tampered = b'{"event":"payment.captured","amount":99999}'
    assert verify_webhook_signature(tampered, signature, SECRET) is False


def test_missing_signature_or_secret_rejected():
    body = b"{}"
    assert verify_webhook_signature(body, "", SECRET) is False
    assert verify_webhook_signature(body, sign(body), "") is False
