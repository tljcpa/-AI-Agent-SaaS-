"""底层能力抽象协议：通过 Protocol 实现接口驱动架构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolSchema:
    """工具定义，供 LLM function-calling 使用。"""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(slots=True)
class ToolCallResult:
    """单次工具调用结果。"""

    tool_name: str
    success: bool
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class StorageProvider(Protocol):
    """文件存储协议，必须按 user_id 做沙箱隔离。"""

    def save_file(self, user_id: int, filename: str, content: bytes) -> str:
        ...

    def list_files(self, user_id: int) -> list[str]:
        ...

    def read_text(self, user_id: int, relative_path: str) -> str:
        ...


class LLMProvider(Protocol):
    """大模型调用协议。"""

    async def generate(self, prompt: str, context: dict | None = None) -> str:
        ...

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSchema],
        context: dict[str, Any] | None = None,
    ) -> ToolCallResult:
        ...


class OfficeAPIProvider(Protocol):
    """办公能力协议（文档排版、报表分析等）。"""

    async def format_document(self, user_id: int, file_path: str, style: str) -> str:
        ...

    async def analyze_report(self, user_id: int, file_path: str) -> str:
        ...
