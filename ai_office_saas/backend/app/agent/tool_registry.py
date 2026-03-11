"""工具注册中心。"""
from __future__ import annotations

from app.adapters.protocols import ToolSchema


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSchema] = {
            "read_word_content": ToolSchema(
                name="read_word_content",
                description="读取 Word 文本内容",
                parameters={"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]},
            ),
            "read_excel_data": ToolSchema(
                name="read_excel_data",
                description="读取 Excel sheet 数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "sheet_name": {"type": "string"},
                    },
                    "required": ["file_id", "sheet_name"],
                },
            ),
        }

    def list(self) -> list[ToolSchema]:
        return list(self._tools.values())
