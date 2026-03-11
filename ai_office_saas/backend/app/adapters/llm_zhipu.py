"""智谱模型适配器（支持基础 function-calling）。"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from app.adapters.protocols import ToolCallResult, ToolSchema


class ZhipuLLMProvider:
    """LLMProvider 的示例实现，可无缝替换为真实 API 调用。"""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def generate(self, prompt: str, context: dict | None = None) -> str:
        await asyncio.sleep(0.2)
        if context:
            return f"[LLM响应] 基于上下文 {context}，建议执行：{prompt[:120]}"
        return f"[LLM响应] {prompt[:200]}"

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSchema],
        context: dict[str, Any] | None = None,
    ) -> ToolCallResult:
        """轻量 mock：根据最后一条用户消息选择工具。"""

        await asyncio.sleep(0.2)
        user_text = ""
        if messages:
            user_text = str(messages[-1].get("content", "")).lower()

        if not tools:
            return ToolCallResult(tool_name="", success=False, content="无可用工具")

        selected = tools[0]
        for tool in tools:
            if tool.name.lower() in user_text:
                selected = tool
                break

        if selected.name in {"read_word_content", "format_word_document"}:
            content = json.dumps({"file_id": "mock-file-id"})
        elif selected.name in {"read_excel_data", "write_excel_data"}:
            content = json.dumps({"file_id": "mock-file-id", "sheet_name": "Sheet1", "data": []})
        else:
            content = json.dumps({"file_id": "mock-file-id"})

        return ToolCallResult(
            tool_name=selected.name,
            success=True,
            content=content,
            raw={"messages": len(messages), "context": context or {}},
        )
