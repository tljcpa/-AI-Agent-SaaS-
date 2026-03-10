"""认证接口：注册与登录（返回 JWT）。"""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.core.security import create_access_token, hash_password, verify_password
from app.models.database import User, session_scope

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


@router.post("/register")
def register(payload: AuthRequest):
    user_id: int | None = None
    with session_scope() as db:
        exists = db.query(User).filter(User.username == payload.username).first()
        if exists:
            raise HTTPException(status_code=400, detail="用户名已存在")

        user = User(username=payload.username, hashed_password=hash_password(payload.password))
        db.add(user)
        db.flush()
        user_id = user.id

    if user_id is None:
        raise HTTPException(status_code=500, detail="用户创建失败")

    token = create_access_token(str(user_id))
    return {"access_token": token, "token_type": "bearer", "user_id": user_id}


@router.post("/login")
def login(payload: AuthRequest):
    with session_scope() as db:
        user = db.query(User).filter(User.username == payload.username).first()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_access_token(str(user.id))
        return {"access_token": token, "token_type": "bearer", "user_id": user.id}
