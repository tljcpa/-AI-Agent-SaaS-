"""智谱 GLM 模型适配器，调用 https://open.bigmodel.cn/api/paas/v4/ 兼容 OpenAI 协议接口"""
from __future__ import annotations

from typing import Any

import httpx

from app.adapters.protocols import ToolCallResult, ToolSchema


class ZhipuLLMProvider:
    """智谱 GLM 的 OpenAI-Compatible Provider 实现。"""

    def __init__(self, api_key: str, model: str, http_client: httpx.AsyncClient) -> None:
        self.api_key = api_key
        self.model = model
        self.http_client = http_client

    async def generate(self, prompt: str, context: dict | None = None) -> str:
        # 生产改造：移除 mock，直接调用智谱官方 Chat Completions 接口。
        content = prompt
        if context:
            content = f"{content}\n上下文：{context}"
        payload = {"model": self.model, "messages": [{"role": "user", "content": content}]}
        resp = await self.http_client.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM 返回了空的 choices，原始响应：{data}")
        message = choices[0].get("message") or {}
        return message.get("content") or ""

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSchema],
        context: dict[str, Any] | None = None,
    ) -> ToolCallResult:
        # 生产改造：工具调用请求与 openai_compat 完全对齐，避免协议差异。
        payload_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
        payload = {"model": self.model, "messages": messages, "tools": payload_tools}
        if context:
            payload["metadata"] = context
        resp = await self.http_client.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM 返回了空的 choices，原始响应：{data}")
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            content = message.get("content", "")
            return ToolCallResult(tool_name="", success=False, content=content, tool_arguments="", raw=data)

        func = tool_calls[0]["function"]
        return ToolCallResult(
            tool_name=func["name"],
            success=True,
            content=message.get("content") or "",
            tool_arguments=func.get("arguments", "{}"),
            raw=data,
        )
