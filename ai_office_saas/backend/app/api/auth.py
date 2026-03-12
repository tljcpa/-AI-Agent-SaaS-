"""认证接口：注册与登录（返回 JWT）。"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import create_access_token, hash_password, verify_password
from app.models.database import User, session_scope

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, payload: AuthRequest):
    if not re.fullmatch(r"[a-zA-Z0-9_一-龥]{3,64}", payload.username):
        raise HTTPException(status_code=400, detail="用户名只能包含字母、数字、下划线或中文")

    user_id: int | None = None
    try:
        with session_scope() as db:
            exists = db.query(User).filter(User.username == payload.username).first()
            if exists:
                raise HTTPException(status_code=400, detail="用户名已存在")

            user = User(username=payload.username, hashed_password=hash_password(payload.password))
            db.add(user)
            db.flush()
            user_id = user.id
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="用户名已存在") from exc

    if user_id is None:
        raise HTTPException(status_code=500, detail="用户创建失败")

    token = create_access_token(str(user_id))
    return {"access_token": token, "token_type": "bearer", "user_id": user_id}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, payload: AuthRequest):
    with session_scope() as db:
        user = db.query(User).filter(User.username == payload.username).first()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_access_token(str(user.id))
        return {"access_token": token, "token_type": "bearer", "user_id": user.id}
