"""安全模块：密码哈希、JWT 签发与校验。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """使用 bcrypt 进行密码哈希。"""

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配。"""

    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """创建访问令牌。"""

    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.security.access_token_expire_minutes)
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.security.jwt_secret, algorithm=settings.security.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """解码访问令牌，失败则抛出 InvalidTokenError。"""

    settings = get_settings()
    return jwt.decode(token, settings.security.jwt_secret, algorithms=[settings.security.jwt_algorithm])


def try_get_subject(token: str) -> str | None:
    """安全地读取 token 中的 sub 字段。"""

    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except InvalidTokenError:
        return None
