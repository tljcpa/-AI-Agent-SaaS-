"""交互式 Agent 引擎：基于事件循环/状态机，实现可中断与可恢复执行。"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.adapters.protocols import LLMProvider, OfficeAPIProvider, StorageProvider
from app.agent.state import AgentPhase, AgentState

Emitter = Callable[[dict], Awaitable[None]]


class AgentEngine:
    """每个会话实例化一个 AgentEngine，用于处理多步任务。"""

    def __init__(self, llm: LLMProvider, storage: StorageProvider, office: OfficeAPIProvider) -> None:
        self.llm = llm
        self.storage = storage
        self.office = office
        self._resume_events: dict[str, asyncio.Event] = {}

    async def start(self, state: AgentState, user_message: str, emit: Emitter) -> None:
        """启动任务执行。"""

        state.task = user_message
        state.phase = AgentPhase.UNDERSTAND
        await emit({"type": "action_progress", "message": "正在理解任务意图..."})

        llm_tip = await self.llm.generate(f"请为以下任务生成三步执行计划：{user_message}")
        state.phase = AgentPhase.PLAN
        state.plan = ["收集资料", "执行办公操作", "输出总结"]
        await emit({"type": "message", "message": llm_tip})
        await emit({"type": "action_progress", "message": f"计划已生成：{state.plan}"})

        state.phase = AgentPhase.WAIT_USER
        state.waiting_action = "confirm_plan"
        self._resume_events[state.session_id] = asyncio.Event()
        await emit(
            {
                "type": "action_confirm",
                "message": "是否确认执行该计划？",
                "payload": {"action": "confirm_plan"},
            }
        )
        await self._resume_events[state.session_id].wait()

        decision = state.context.get("confirm_plan", "").lower()
        if decision != "confirm":
            state.phase = AgentPhase.DONE
            await emit({"type": "message", "message": "任务已取消。你可以重新描述需求。"})
            self._resume_events.pop(state.session_id, None)
            return

        state.phase = AgentPhase.EXECUTE
        await emit({"type": "action_progress", "message": "开始执行任务步骤..."})

        files = self.storage.list_files(state.user_id)
        if not files:
            state.phase = AgentPhase.WAIT_USER
            state.waiting_action = "need_file"
            self._resume_events[state.session_id] = asyncio.Event()
            await emit(
                {
                    "type": "action_ask_user",
                    "message": "未检测到可用文件，请上传后输入“已上传”继续。",
                    "payload": {"action": "need_file"},
                }
            )
            await self._resume_events[state.session_id].wait()
            files = self.storage.list_files(state.user_id)

        target = files[0]
        await emit({"type": "action_progress", "message": f"正在处理文件：{target}"})
        format_result = await self.office.format_document(state.user_id, target, "商务简洁")
        report = await self.office.analyze_report(state.user_id, target)
        summary = await self.llm.generate("请总结以下结果", {"format": format_result, "report": report})

        state.phase = AgentPhase.DONE
        await emit({"type": "message", "message": format_result})
        await emit({"type": "message", "message": report})
        await emit({"type": "message", "message": summary})
        await emit({"type": "action_progress", "message": "任务执行完成。"})
        self._resume_events.pop(state.session_id, None)

    async def resume(self, state: AgentState, action: str, value: str, emit: Emitter) -> None:
        """恢复挂起状态。"""

        if state.phase != AgentPhase.WAIT_USER:
            await emit({"type": "message", "message": "当前无需人工介入。"})
            return

        if state.waiting_action != action:
            await emit({"type": "message", "message": f"收到无效动作 {action}，期望 {state.waiting_action}"})
            return

        state.context[action] = value
        state.waiting_action = None
        if state.session_id in self._resume_events:
            self._resume_events[state.session_id].set()

