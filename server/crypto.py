from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet

from .settings import settings


_fernet_instance: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    secret = settings.CRYPTO_SECRET
    if secret:
        key = secret.encode("utf-8")
    else:
        key = base64.urlsafe_b64encode(os.urandom(32))
    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_text(plaintext: str) -> str:
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(ciphertext: str) -> str:
    f = _get_fernet()
    plain = f.decrypt(ciphertext.encode("utf-8"))
    return plain.decode("utf-8")
