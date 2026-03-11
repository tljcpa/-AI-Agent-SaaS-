"""工具注册中心。"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.adapters.protocols import ToolSchema

ToolCallable = Callable[..., Awaitable[str]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSchema] = {}
        self._handlers: dict[str, ToolCallable] = {}

    def register(self, schema: ToolSchema, fn: ToolCallable) -> None:
        self._tools[schema.name] = schema
        self._handlers[schema.name] = fn

    def list(self) -> list[ToolSchema]:
        return list(self._tools.values())

    def get_schema(self, tool_name: str) -> ToolSchema:
        schema = self._tools.get(tool_name)
        if schema is None:
            raise KeyError(f"tool not found: {tool_name}")
        return schema

    async def dispatch(self, tool_name: str, user_id: int, arguments: dict) -> str:
        fn = self._handlers.get(tool_name)
        if fn is None:
            raise KeyError(f"tool not found: {tool_name}")
        clean_args = {k: v for k, v in arguments.items() if k != "user_id"}
        return await fn(user_id=user_id, **clean_args)
