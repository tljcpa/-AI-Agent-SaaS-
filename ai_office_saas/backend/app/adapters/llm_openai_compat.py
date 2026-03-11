"""OpenAI 兼容接口的 LLM 适配器。"""
from __future__ import annotations

from typing import Any

import httpx

from app.adapters.protocols import ToolCallResult, ToolSchema


class OpenAICompatLLMProvider:
    """通过 OpenAI-Compatible Chat Completions 协议调用模型。"""

    def __init__(self, base_url: str, api_key: str, model: str, http_client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.http_client = http_client

    async def generate(self, prompt: str, context: dict | None = None) -> str:
        messages = [{"role": "user", "content": prompt if not context else f"{prompt}\n上下文:{context}"}]
        payload = {"model": self.model, "messages": messages}
        resp = await self.http_client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def tool_call(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolSchema],
        context: dict[str, Any] | None = None,
    ) -> ToolCallResult:
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
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        message = data["choices"][0]["message"]
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
