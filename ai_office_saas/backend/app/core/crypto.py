"""Token 加解密工具。"""
from __future__ import annotations

import base64
import os
import warnings
from pathlib import Path

from cryptography.fernet import Fernet

_DEV_KEY_PATH = Path("./data/.dev_fernet_key")


def _load_or_create_dev_key() -> bytes:
    if _DEV_KEY_PATH.exists():
        return _DEV_KEY_PATH.read_bytes().strip()

    _DEV_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    dev_key = base64.urlsafe_b64encode(os.urandom(32))
    _DEV_KEY_PATH.write_bytes(dev_key)
    os.chmod(_DEV_KEY_PATH, 0o600)
    return dev_key


def _build_fernet() -> Fernet:
    key = os.getenv("TOKEN_ENCRYPT_KEY")
    if key:
        return Fernet(key.encode("utf-8"))

    app_env = os.getenv("APP_ENV", "development")
    if app_env == "production":
        raise RuntimeError("生产环境必须设置 TOKEN_ENCRYPT_KEY")

    dev_key = _load_or_create_dev_key()
    warnings.warn(f"TOKEN_ENCRYPT_KEY 未设置，已使用本地开发密钥文件: {_DEV_KEY_PATH}", stacklevel=2)
    return Fernet(dev_key)


_FERNET: Fernet = _build_fernet()


def encrypt_token(plaintext: str) -> str:
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    return _FERNET.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
