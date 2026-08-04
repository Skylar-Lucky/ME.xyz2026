"""Symmetric encryption for user-supplied model API keys (BYOK).

AES-256-GCM with a key from BYOK_ENCRYPTION_KEY (env). Same trust model as
JWT_SECRET: a dev-only fallback default, production must override in .env.
Never log plaintext or ciphertext — only key_last4 is safe to log.
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

_DEV_ONLY_DEFAULT_PHRASE = "dev-only-change-me-mexyz-please-use-env-in-production"


def _load_key() -> bytes:
    raw = os.getenv("BYOK_ENCRYPTION_KEY", "").strip()
    if not raw:
        # Dev fallback: derive a stable 32-byte key from a fixed phrase (never used in prod).
        return hashlib.sha256(_DEV_ONLY_DEFAULT_PHRASE.encode("utf-8")).digest()
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as e:
        raise RuntimeError("BYOK_ENCRYPTION_KEY 不是合法的 base64url 字符串") from e
    if len(key) != 32:
        raise RuntimeError("BYOK_ENCRYPTION_KEY 解码后必须是 32 字节（AES-256）")
    return key


_AESGCM = AESGCM(_load_key())


def encrypt_secret(plaintext: str) -> str:
    nonce = os.urandom(12)
    ciphertext = _AESGCM.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_secret(token: str) -> str:
    raw = base64.urlsafe_b64decode(token.encode("utf-8"))
    nonce, ciphertext = raw[:12], raw[12:]
    return _AESGCM.decrypt(nonce, ciphertext, None).decode("utf-8")
