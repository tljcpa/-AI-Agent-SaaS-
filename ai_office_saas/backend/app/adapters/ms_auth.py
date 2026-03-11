"""Microsoft Graph OAuth2：token 持久化与自动续期。"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import update

from app.core.config import MSGraphConfig
from app.core.crypto import decrypt_token, encrypt_token
from app.models.database import UserOAuthToken, session_scope

logger = logging.getLogger(__name__)


class MSAuthService:
    def __init__(self, config: MSGraphConfig, http_client: httpx.AsyncClient) -> None:
        self.config = config
        self.http_client = http_client
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
        response = await self.http_client.post(f"{self.authority}/token", data=payload)
        response.raise_for_status()
        data = response.json()
        await asyncio.to_thread(self._save_token_sync, user_id, data)
        logger.info("OAuth code exchange completed", extra={"user_id": user_id})

    async def get_valid_access_token(self, user_id: int) -> str:
        for retry in range(5):
            token_row, should_wait = await asyncio.to_thread(self._claim_or_get_token_sync, user_id)
            if should_wait:
                wait_seconds = min(0.1 * (2 ** retry), 2.0)
                logger.debug("OAuth token refresh in progress, waiting", extra={"user_id": user_id, "retry": retry + 1, "wait_seconds": wait_seconds})
                await asyncio.sleep(wait_seconds)
                continue
            if token_row is None:
                raise ValueError("用户尚未授权 OneDrive")

            if token_row["access_token"]:
                return token_row["access_token"]

            token_id = token_row["id"]
            refresh_token = token_row["refresh_token"]
            try:
                data = await self._refresh(refresh_token)
                await asyncio.to_thread(self._save_token_sync, user_id, data)
                logger.info("OAuth token refreshed", extra={"user_id": user_id})
                return str(data["access_token"])
            finally:
                if token_id is not None:
                    await asyncio.to_thread(self._clear_refreshing_sync, token_id)

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
        response = await self.http_client.post(f"{self.authority}/token", data=payload)
        response.raise_for_status()
        return response.json()

    def _claim_or_get_token_sync(self, user_id: int) -> tuple[dict | None, bool]:
        token_id: int | None = None
        with session_scope() as db:
            token = (
                db.query(UserOAuthToken)
                .filter(UserOAuthToken.user_id == user_id, UserOAuthToken.provider == "onedrive")
                .order_by(UserOAuthToken.updated_at.desc())
                .first()
            )
            if token is None:
                return None, False

            now = datetime.now(timezone.utc)
            if token.expires_at > now + timedelta(seconds=60):
                return {"id": token.id, "access_token": decrypt_token(token.access_token), "refresh_token": ""}, False

            claim_stmt = (
                update(UserOAuthToken)
                .where(UserOAuthToken.id == token.id, UserOAuthToken.is_refreshing.is_(False))
                .values(is_refreshing=True)
            )
            claim_result = db.execute(claim_stmt)
            if claim_result.rowcount == 0:
                return None, True

            token_id = token.id
            return {
                "id": token_id,
                "access_token": "",
                "refresh_token": decrypt_token(token.refresh_token),
            }, False

    def _clear_refreshing_sync(self, token_id: int) -> None:
        with session_scope() as clear_db:
            clear_db.execute(
                update(UserOAuthToken)
                .where(UserOAuthToken.id == token_id)
                .values(is_refreshing=False)
            )

    def _save_token_sync(self, user_id: int, token_payload: dict) -> None:
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
