"""Token 加解密工具。"""
from __future__ import annotations

import base64
import os
import warnings

from cryptography.fernet import Fernet


def _build_fernet() -> Fernet:
    key = os.getenv("TOKEN_ENCRYPT_KEY")
    if key:
        return Fernet(key.encode("utf-8"))

    app_env = os.getenv("APP_ENV", "development")
    if app_env != "development":
        raise RuntimeError("生产环境必须设置 TOKEN_ENCRYPT_KEY")

    warnings.warn("TOKEN_ENCRYPT_KEY 未设置，已生成临时开发密钥。重启后将无法解密旧 token。", stacklevel=2)
    dev_key = base64.urlsafe_b64encode(os.urandom(32))
    return Fernet(dev_key)


_FERNET: Fernet | None = None


def encrypt_token(plaintext: str) -> str:
    global _FERNET
    if _FERNET is None:
        _FERNET = _build_fernet()
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    global _FERNET
    if _FERNET is None:
        _FERNET = _build_fernet()
    return _FERNET.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
