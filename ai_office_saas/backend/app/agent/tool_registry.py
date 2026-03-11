"""工具注册中心。"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.adapters.protocols import ToolSchema

ToolCallable = Callable[..., Awaitable[str]]


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
            "format_word_document": ToolSchema(
                name="format_word_document",
                description="按指令格式化 Word 文档",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "style_instructions": {"type": "string"},
                    },
                    "required": ["file_id", "style_instructions"],
                },
            ),
            "write_excel_data": ToolSchema(
                name="write_excel_data",
                description="写入 Excel 数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "sheet_name": {"type": "string"},
                        "data": {"type": "array"},
                    },
                    "required": ["file_id", "sheet_name", "data"],
                },
            ),
        }
        self._handlers: dict[str, ToolCallable] = {}

    def register(self, schema: ToolSchema, fn: ToolCallable) -> None:
        self._tools[schema.name] = schema
        self._handlers[schema.name] = fn

    def list(self) -> list[ToolSchema]:
        return list(self._tools.values())

    async def dispatch(self, tool_name: str, arguments: dict) -> str:
        fn = self._handlers.get(tool_name)
        if fn is None:
            raise KeyError(f"tool not found: {tool_name}")
        return await fn(**arguments)
