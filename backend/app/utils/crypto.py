"""Symmetric encryption for sensitive values stored in the database.

Uses Fernet (AES-128-CBC + HMAC-SHA256) derived from the application secret_key.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the application secret_key."""
    secret = get_settings().secret_key.encode()
    # Fernet requires a 32-byte url-safe base64 key. Derive one via SHA-256.
    key_bytes = hashlib.sha256(secret).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value, returning a base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext.

    Raises ValueError if the ciphertext is invalid or tampered with.
    """
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt value — invalid key or corrupted data")
