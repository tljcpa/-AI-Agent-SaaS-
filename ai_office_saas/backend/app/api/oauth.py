"""OAuth 路由：OneDrive delegated 授权。"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.adapters.ms_auth import MSAuthService
from app.core.container import AppContainer
from app.core.security import try_get_subject
from app.models.database import OAuthStateCache, session_scope

router = APIRouter(prefix="/oauth", tags=["oauth"])
logger = logging.getLogger(__name__)


def get_oauth_service(request: Request) -> MSAuthService:
    container: AppContainer = request.app.state.container
    return container.auth_service


@router.get("/redirect")
def oauth_redirect(
    request: Request,
    token: str = Query(default=""),
    service: MSAuthService = Depends(get_oauth_service),
):
    auth_header = request.headers.get("Authorization", "")
    header_token = auth_header.removeprefix("Bearer ").strip()
    effective_token = header_token or token
    user_sub = try_get_subject(effective_token)
    if not user_sub or not user_sub.isdigit():
        logger.warning("OAuth redirect unauthorized")
        raise HTTPException(status_code=401, detail="未登录")

    user_id = int(user_sub)
    state = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    with session_scope() as db:
        # 修复：写入新 state 前清理同用户的过期记录，避免缓存表无限增长。
        db.query(OAuthStateCache).filter(
            OAuthStateCache.user_id == user_id,
            OAuthStateCache.expires_at <= datetime.now(timezone.utc),
        ).delete()
        db.add(OAuthStateCache(state_token=state, user_id=user_id, expires_at=expires_at))

    url = service.build_authorization_url(state)
    logger.info("OAuth redirect generated", extra={"user_id": user_id})
    return RedirectResponse(url=url)


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    service: MSAuthService = Depends(get_oauth_service),
):
    if not re.fullmatch(r"[A-Za-z0-9\-_.~]{1,2048}", code):
        raise HTTPException(status_code=400, detail="无效的授权码格式")

    with session_scope() as db:
        state_row = (
            db.query(OAuthStateCache)
            .filter(
                OAuthStateCache.state_token == state,
                OAuthStateCache.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )
        if state_row is None:
            raise HTTPException(status_code=400, detail="state 非法或已过期")
        user_id = state_row.user_id
        db.delete(state_row)
        db.flush()

    try:
        await service.exchange_code(user_id, code)
    except Exception as e:
        logger.error("OAuth callback exchange failed", exc_info=e)
        raise HTTPException(status_code=502, detail="OneDrive 授权失败，请稍后重试")

    logger.info("OAuth callback completed", extra={"user_id": user_id})
    return {"ok": True, "message": "OneDrive 授权成功，可继续发起任务"}
