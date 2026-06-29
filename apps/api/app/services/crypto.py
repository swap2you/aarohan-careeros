import base64
import hashlib
import json

from cryptography.fernet import Fernet

from app.config import settings


def _fernet_for_source(source: str) -> Fernet:
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        if settings.app_env in {"test", "local"} and settings.app_secret:
            source = settings.app_secret
        else:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be configured for OAuth token encryption")
    else:
        source = settings.token_encryption_key
    return _fernet_for_source(source)


def encrypt_payload(payload: dict) -> str:
    return _fernet().encrypt(json.dumps(payload).encode("utf-8")).decode("utf-8")


def decrypt_payload(value: str) -> dict:
    sources: list[str] = []
    if settings.token_encryption_key:
        sources.append(settings.token_encryption_key)
    if settings.app_env in {"test", "local", "development"} and settings.app_secret:
        if settings.app_secret not in sources:
            sources.append(settings.app_secret)
    last_error: Exception | None = None
    for source in sources:
        try:
            return json.loads(_fernet_for_source(source).decrypt(value.encode("utf-8")).decode("utf-8"))
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError("Unable to decrypt payload")
