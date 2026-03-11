"""Microsoft Graph OAuth2：token 持久化与自动续期。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import update

from app.core.config import MSGraphConfig
from app.core.crypto import decrypt_token, encrypt_token
from app.models.database import UserOAuthToken, session_scope


class MSAuthService:
    def __init__(self, config: MSGraphConfig) -> None:
        self.config = config
        self.authority = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0"

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(self.config.scopes),
            "state": state,
        }
        return f"{self.authority}/authorize?{urlencode(params)}"

    async def exchange_code(self, user_id: int, code: str) -> None:
        payload = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.authority}/token", data=payload)
            response.raise_for_status()
            data = response.json()
        self._save_token(user_id, data)

    async def get_valid_access_token(self, user_id: int) -> str:
        for _ in range(5):
            token_id = 0
            with session_scope() as db:
                token = (
                    db.query(UserOAuthToken)
                    .filter(UserOAuthToken.user_id == user_id, UserOAuthToken.provider == "onedrive")
                    .order_by(UserOAuthToken.updated_at.desc())
                    .first()
                )
                if token is None:
                    raise ValueError("用户尚未授权 OneDrive")

                now = datetime.now(timezone.utc)
                if token.expires_at > now + timedelta(seconds=60):
                    return decrypt_token(token.access_token)

                claim_stmt = (
                    update(UserOAuthToken)
                    .where(UserOAuthToken.id == token.id, UserOAuthToken.is_refreshing.is_(False))
                    .values(is_refreshing=True)
                )
                claim_result = db.execute(claim_stmt)
                if claim_result.rowcount == 0:
                    continue_refresh = True
                else:
                    continue_refresh = False
                    token_id = token.id
                    refresh_token = decrypt_token(token.refresh_token)

            if continue_refresh:
                await asyncio.sleep(1)
                continue

            try:
                data = await self._refresh(refresh_token)
                self._save_token(user_id, data)
                return str(data["access_token"])
            finally:
                with session_scope() as clear_db:
                    clear_db.execute(
                        update(UserOAuthToken)
                        .where(UserOAuthToken.id == token_id)
                        .values(is_refreshing=False)
                    )

        raise RuntimeError("Token 刷新重试次数已耗尽")

    async def _refresh(self, refresh_token: str) -> dict:
        payload = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.authority}/token", data=payload)
            response.raise_for_status()
            return response.json()

    def _save_token(self, user_id: int, token_payload: dict) -> None:
        expires_in = int(token_payload.get("expires_in", 3600))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        access_token = encrypt_token(str(token_payload["access_token"]))
        refresh_raw = str(token_payload.get("refresh_token", ""))
        refresh_token = encrypt_token(refresh_raw) if refresh_raw else ""

        with session_scope() as db:
            row = (
                db.query(UserOAuthToken)
                .filter(UserOAuthToken.user_id == user_id, UserOAuthToken.provider == "onedrive")
                .first()
            )
            if row is None:
                row = UserOAuthToken(
                    user_id=user_id,
                    provider="onedrive",
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    is_refreshing=False,
                )
                db.add(row)
            else:
                row.access_token = access_token
                if refresh_token:
                    row.refresh_token = refresh_token
                row.expires_at = expires_at
                row.is_refreshing = False
