"""办公 API 适配器（E5 Mock）。"""
from __future__ import annotations

import asyncio


class E5OfficeProvider:
    """OfficeAPIProvider 的基础实现，便于后续接入真实办公系统。"""

    async def read_word_content(self, user_id: int, file_id: str) -> str:
        await asyncio.sleep(0.1)
        return f"用户 {user_id} 读取 Word 文件 {file_id}（mock）"

    async def format_word_document(self, user_id: int, file_id: str, style_instructions: str) -> str:
        await asyncio.sleep(0.2)
        return f"用户 {user_id} 的 Word {file_id} 已按 {style_instructions} 完成格式化（mock）"

    async def read_excel_data(self, user_id: int, file_id: str, sheet_name: str) -> str:
        await asyncio.sleep(0.1)
        return f"用户 {user_id} 读取 Excel {file_id}/{sheet_name}（mock）"

    async def write_excel_data(self, user_id: int, file_id: str, sheet_name: str, data: list) -> str:
        await asyncio.sleep(0.2)
        return f"用户 {user_id} 向 Excel {file_id}/{sheet_name} 写入 {len(data)} 行（mock）"

