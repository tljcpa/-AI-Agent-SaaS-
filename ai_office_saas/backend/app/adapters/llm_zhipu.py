"""智谱模型适配器（当前实现为可替换的 Mock 骨架）。"""
from __future__ import annotations

import asyncio


class ZhipuLLMProvider:
    """LLMProvider 的示例实现，可无缝替换为真实 API 调用。"""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def generate(self, prompt: str, context: dict | None = None) -> str:
        # 这里模拟大模型响应延迟，真实环境中可通过 httpx 调用供应商接口。
        await asyncio.sleep(0.2)
        if context:
            return f"[LLM响应] 基于上下文 {context}，建议执行：{prompt[:120]}"
        return f"[LLM响应] {prompt[:200]}"
