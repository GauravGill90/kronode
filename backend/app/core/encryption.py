"""Symmetric encryption for secrets at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) with the ENCRYPTION_KEY env var.
When no key is set, fields are stored/returned as plaintext (dev mode).
"""
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = settings.encryption_key
    if not key:
        return None
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY: {e}")
        return None


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string. Returns ciphertext or plaintext if no key configured."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a string. Returns plaintext if decryption fails (legacy unencrypted data)."""
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Likely unencrypted legacy data — return as-is
        return ciphertext


def generate_encryption_key() -> str:
    """Generate a new Fernet key for use as ENCRYPTION_KEY."""
    return Fernet.generate_key().decode()
