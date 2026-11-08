"""Symmetric encryption for secrets stored in the database (camera passwords).

A Fernet key is derived deterministically from the application secret key so
that no extra key management is required, while stored credentials never sit in
the database in clear text.
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)


def derive_fernet_key(secret_key: str) -> bytes:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class SecretBox:
    """Encrypt/decrypt short secrets with Fernet."""

    def __init__(self, secret_key: str):
        self._fernet = Fernet(derive_fernet_key(secret_key))

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        if plaintext is None or plaintext == "":
            return None
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            log.warning("Failed to decrypt stored secret")
            return None

    def mask(self, token: Optional[str]) -> str:
        """Return a display mask that never leaks the secret."""
        if not token:
            return ""
        return "********"
