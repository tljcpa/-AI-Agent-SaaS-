"""交互式 Agent 引擎：ReAct 循环 + 可恢复状态机。"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.adapters.protocols import LLMProvider, OfficeAPIProvider, StorageProvider
from app.agent.state import AgentPhase, AgentState
from app.agent.tool_registry import ToolRegistry

Emitter = Callable[[dict], Awaitable[None]]


class AgentEngine:
    def __init__(
        self,
        llm: LLMProvider,
        storage: StorageProvider,
        office: OfficeAPIProvider,
        tool_registry: ToolRegistry,
    ) -> None:
        self.llm = llm
        self.storage = storage
        self.office = office
        self.tool_registry = tool_registry
        self._resume_events: dict[str, asyncio.Event] = {}
        self._resume_events_lock = asyncio.Lock()
        self.max_steps = 5

    @staticmethod
    def _event_key(state: AgentState) -> str:
        return f"{state.user_id}:{state.session_id}"

    async def _register_resume_event(self, state: AgentState) -> asyncio.Event:
        key = self._event_key(state)
        async with self._resume_events_lock:
            event = asyncio.Event()
            self._resume_events[key] = event
        return event

    async def _pop_resume_event(self, state: AgentState) -> None:
        key = self._event_key(state)
        async with self._resume_events_lock:
            self._resume_events.pop(key, None)

    async def start(self, state: AgentState, user_message: str, emit: Emitter) -> None:
        try:
            state.task = user_message
            state.phase = AgentPhase.UNDERSTAND
            state.messages.append({"role": "user", "content": user_message})
            await emit({"type": "action_progress", "message": "进入 ReAct 执行循环..."})

            files = self.storage.list_files(state.user_id)
            if not files:
                state.phase = AgentPhase.WAIT_USER
                state.waiting_action = "need_file"
                event = await self._register_resume_event(state)
                await emit(
                    {
                        "type": "action_ask_user",
                        "message": "未检测到可用文件。若使用 OneDrive，请先访问 /api/oauth/redirect 授权。",
                        "payload": {"action": "need_file"},
                    }
                )
                await event.wait()

            state.phase = AgentPhase.EXECUTE
            for i in range(self.max_steps):
                state.step_count += 1
                tools = self.tool_registry.list()
                decision = await self.llm.tool_call(state.messages, tools, context={"step": i + 1})
                await emit({"type": "action_progress", "message": f"Step {i + 1}: {decision.content}"})
                state.messages.append({"role": "assistant", "content": decision.content})

                if i >= 1:
                    break

            summary = await self.llm.generate("请给出当前任务总结", {"steps": state.step_count})
            await emit({"type": "message", "message": summary})
            state.phase = AgentPhase.DONE
        finally:
            await self._pop_resume_event(state)

    async def resume(self, state: AgentState, action: str, value: str, emit: Emitter) -> None:
        if state.phase != AgentPhase.WAIT_USER:
            await emit({"type": "message", "message": "当前无需人工介入。"})
            return
        if state.waiting_action != action:
            await emit({"type": "message", "message": f"收到无效动作 {action}，期望 {state.waiting_action}"})
            return

        state.context[action] = value
        state.waiting_action = None
        key = self._event_key(state)
        async with self._resume_events_lock:
            event = self._resume_events.get(key)
        if event:
            event.set()
