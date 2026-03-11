"""OAuth 路由：OneDrive delegated 授权。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.adapters.ms_auth import MSAuthService
from app.core.config import get_settings
from app.core.security import try_get_subject

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
    url = _service().build_authorization_url(int(user_sub))
    return RedirectResponse(url=url)


@router.get("/callback")
def oauth_callback(code: str = Query(...), state: str = Query(...)):
    if not state.isdigit():
        raise HTTPException(status_code=400, detail="state 非法")
    _service().exchange_code(int(state), code)
    return {"ok": True, "message": "OneDrive 授权成功，可继续发起任务"}
