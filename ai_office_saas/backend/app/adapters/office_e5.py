"""办公 API 适配器（E5 Mock）。"""
from __future__ import annotations

import asyncio


class E5OfficeProvider:
    """OfficeAPIProvider 的基础实现，便于后续接入真实办公系统。"""

    async def format_document(self, user_id: int, file_path: str, style: str) -> str:
        await asyncio.sleep(0.3)
        return f"用户 {user_id} 的文档 {file_path} 已按 {style} 风格完成排版。"

    async def analyze_report(self, user_id: int, file_path: str) -> str:
        await asyncio.sleep(0.3)
        return f"用户 {user_id} 的报表 {file_path} 分析完成：营收上升 12%，成本下降 4%。"
