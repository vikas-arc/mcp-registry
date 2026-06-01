from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import get_settings

_fernet = Fernet(get_settings().master_encryption_key.encode())


def encrypt(plaintext: str) -> bytes:
    return _fernet.encrypt(plaintext.encode())


def decrypt(token: bytes) -> str:
    return _fernet.decrypt(token).decode()
