"""Microsoft Graph OAuth2：token 持久化与自动续期。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import MSGraphConfig
from app.models.database import UserOAuthToken, session_scope


class MSAuthService:
    def __init__(self, config: MSGraphConfig) -> None:
        self.config = config
        self.authority = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0"

    def build_authorization_url(self, user_id: int) -> str:
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(self.config.scopes),
            "state": str(user_id),
        }
        return f"{self.authority}/authorize?{urlencode(params)}"

    def exchange_code(self, user_id: int, code: str) -> None:
        payload = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
        }
        with httpx.Client(timeout=30) as client:
            response = client.post(f"{self.authority}/token", data=payload)
            response.raise_for_status()
            data = response.json()
        self._save_token(user_id, data)

    def get_valid_access_token(self, user_id: int) -> str:
        with session_scope() as db:
            token = (
                db.query(UserOAuthToken)
                .filter(UserOAuthToken.user_id == user_id, UserOAuthToken.provider == "onedrive")
                .order_by(UserOAuthToken.updated_at.desc())
                .first()
            )
            if token is None:
                raise ValueError("用户尚未授权 OneDrive")
            if token.expires_at > datetime.now(timezone.utc) + timedelta(seconds=60):
                return token.access_token
            refresh_token = token.refresh_token

        data = self._refresh(refresh_token)
        self._save_token(user_id, data)
        return str(data["access_token"])

    def _refresh(self, refresh_token: str) -> dict:
        payload = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
        }
        with httpx.Client(timeout=30) as client:
            response = client.post(f"{self.authority}/token", data=payload)
            response.raise_for_status()
            return response.json()

    def _save_token(self, user_id: int, token_payload: dict) -> None:
        expires_in = int(token_payload.get("expires_in", 3600))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        access_token = str(token_payload["access_token"])
        refresh_token = str(token_payload.get("refresh_token", ""))

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
                )
                db.add(row)
            else:
                row.access_token = access_token
                if refresh_token:
                    row.refresh_token = refresh_token
                row.expires_at = expires_at
