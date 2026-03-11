"""底层能力抽象协议：通过 Protocol 实现接口驱动架构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(slots=True)
class ToolCallResult:
    tool_name: str
    success: bool
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class StorageProvider(Protocol):
    async def save_file(self, user_id: int, filename: str, content: bytes) -> str: ...
    async def list_files(self, user_id: int) -> list[str]: ...
    async def read_text(self, user_id: int, relative_path: str) -> str: ...


class LLMProvider(Protocol):
    async def generate(self, prompt: str, context: dict | None = None) -> str: ...
    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSchema],
        context: dict[str, Any] | None = None,
    ) -> ToolCallResult: ...


class OfficeAPIProvider(Protocol):
    async def read_word_content(self, user_id: int, file_id: str) -> str: ...
    async def format_word_document(self, user_id: int, file_id: str, style_instructions: str) -> str: ...
    async def read_excel_data(self, user_id: int, file_id: str, sheet_name: str) -> str: ...
    async def write_excel_data(self, user_id: int, file_id: str, sheet_name: str, data: list) -> str: ...
    async def format_document(self, user_id: int, file_path: str, style: str) -> str: ...
    async def analyze_report(self, user_id: int, file_path: str) -> str: ...
