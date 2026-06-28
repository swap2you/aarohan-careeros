import base64
import hashlib
import json

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    source = settings.token_encryption_key or settings.app_secret
    if not source:
        raise ValueError("TOKEN_ENCRYPTION_KEY or APP_SECRET must be configured")
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_payload(payload: dict) -> str:
    return _fernet().encrypt(json.dumps(payload).encode("utf-8")).decode("utf-8")


def decrypt_payload(value: str) -> dict:
    return json.loads(_fernet().decrypt(value.encode("utf-8")).decode("utf-8"))
