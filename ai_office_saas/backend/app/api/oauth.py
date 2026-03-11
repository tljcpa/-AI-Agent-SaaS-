"""OAuth 路由：OneDrive delegated 授权。"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.adapters.ms_auth import MSAuthService
from app.core.config import get_settings
from app.core.security import try_get_subject
from app.models.database import OAuthStateCache, session_scope

router = APIRouter(prefix="/oauth", tags=["oauth"])


def _service() -> MSAuthService:
    return MSAuthService(get_settings().ms_graph)


@router.get("/redirect")
def oauth_redirect(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    user_sub = try_get_subject(token)
    if not user_sub or not user_sub.isdigit():
        raise HTTPException(status_code=401, detail="未登录")

    user_id = int(user_sub)
    state = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    with session_scope() as db:
        db.add(OAuthStateCache(state_token=state, user_id=user_id, expires_at=expires_at))

    url = _service().build_authorization_url(state)
    return RedirectResponse(url=url)


@router.get("/callback")
async def oauth_callback(code: str = Query(...), state: str = Query(...)):
    with session_scope() as db:
        state_row = db.query(OAuthStateCache).filter(OAuthStateCache.state_token == state).first()
        if state_row is None or state_row.expires_at <= datetime.now(timezone.utc):
            if state_row is not None:
                db.delete(state_row)
            raise HTTPException(status_code=400, detail="state 非法或已过期")

        user_id = state_row.user_id
        db.delete(state_row)

    await _service().exchange_code(user_id, code)
    return {"ok": True, "message": "OneDrive 授权成功，可继续发起任务"}
