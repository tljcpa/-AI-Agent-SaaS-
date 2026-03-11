"""OneDrive 存储实现（基于 Microsoft Graph）。"""
from __future__ import annotations

import base64
from pathlib import PurePosixPath

import httpx

from app.adapters.ms_auth import MSAuthService


class OneDriveStorageProvider:
    def __init__(self, auth_service: MSAuthService, root_path: str = "/") -> None:
        self.auth_service = auth_service
        self.root_path = root_path.strip("/")

    async def _headers(self, user_id: int) -> dict[str, str]:
        token = await self.auth_service.get_valid_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    def _scoped_path(self, user_id: int, filename: str) -> str:
        safe_name = PurePosixPath(filename).name
        if filename == "":
            safe_name = ""
        if safe_name and safe_name.startswith("."):
            raise ValueError(f"非法文件名: {filename!r}")
        if filename and not safe_name:
            raise ValueError(f"非法文件名: {filename!r}")

        prefix = f"{self.root_path}/" if self.root_path else ""
        base = f"{prefix}user_{user_id}"
        return f"{base}/{safe_name}" if safe_name else base

    async def save_file(self, user_id: int, filename: str, content: bytes) -> str:
        path = self._scoped_path(user_id, filename)
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{path}:/content"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(url, headers=await self._headers(user_id), content=content)
            resp.raise_for_status()
        return path

    async def list_files(self, user_id: int) -> list[str]:
        base = self._scoped_path(user_id, "")
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{base}:/children"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=await self._headers(user_id))
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            payload = resp.json()
        return [item["name"] for item in payload.get("value", []) if "file" in item]

    async def read_text(self, user_id: int, relative_path: str) -> str:
        path = self._scoped_path(user_id, relative_path)
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{path}:/content"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=await self._headers(user_id))
            resp.raise_for_status()
        content = resp.content
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(content).decode("ascii")
