"""交互式 Agent 引擎：ReAct 循环 + 可恢复状态机。"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from app.adapters.protocols import LLMProvider, OfficeAPIProvider, StorageProvider
from app.agent.state import AgentPhase, AgentState
from app.agent.tool_registry import ToolRegistry

Emitter = Callable[[dict], Awaitable[None]]
logger = logging.getLogger(__name__)


class AgentEngine:
    def __init__(
        self,
        llm: LLMProvider,
        storage: StorageProvider,
        office: OfficeAPIProvider,
        tool_registry: ToolRegistry,
        max_steps: int = 5,
    ) -> None:
        self.llm = llm
        self.storage = storage
        self.office = office
        self.tool_registry = tool_registry
        self._resume_events: dict[str, asyncio.Event] = {}
        self._resume_events_lock = asyncio.Lock()
        self.max_steps = max_steps
        self.max_message_history: int = 40

    @staticmethod
    def _event_key(state: AgentState) -> str:
        return f"{state.user_id}:{state.session_id}"

    # 注册 WAIT_USER 阶段对应的唤醒事件，所有权交给 start() 协程及其 finally 清理。
    async def _register_resume_event(self, state: AgentState) -> asyncio.Event:
        key = self._event_key(state)
        async with self._resume_events_lock:
            event = asyncio.Event()
            self._resume_events[key] = event
        return event

    # 释放事件所有权；由 start() finally 与 resume() 成功唤醒后调用，必须保持幂等。
    async def _pop_resume_event(self, state: AgentState) -> None:
        key = self._event_key(state)
        async with self._resume_events_lock:
            self._resume_events.pop(key, None)

    async def start(self, state: AgentState, user_message: str, emit: Emitter) -> None:
        # UNDERSTAND/PLAN 阶段为未来扩展预留，当前版本直接从 IDLE 进入 EXECUTE。
        try:
            logger.info("Agent start", extra={"session_id": state.session_id, "user_id": state.user_id})
            state.task = user_message
            state.messages.append({"role": "user", "content": user_message})
            state.phase = AgentPhase.EXECUTE
            await emit({"type": "action_progress", "message": "进入 ReAct 执行循环..."})

            async def _fetch_and_inject_files() -> bool:
                """获取文件列表并注入 system 消息。返回 True 表示有文件，False 表示无文件。"""
                try:
                    files = await self.storage.list_files(state.user_id)
                except Exception as e:
                    logger.error("Failed to list files", exc_info=e)
                    await emit({"type": "error", "message": "获取文件列表失败，请检查存储配置后重试"})
                    state.phase = AgentPhase.ERROR
                    return False
                if files:
                    file_list_str = "\n".join(f"- {name}" for name in files)
                    system_content = (
                        "你是一个办公助手 Agent，可以调用工具操作用户文件。\n"
                        f"当前用户拥有以下文件（调用工具时 file_id 直接使用文件名）：\n{file_list_str}\n"
                        "请根据用户任务描述，选择合适的工具和文件完成操作。"
                    )
                    # 如果 messages 里已有 system 消息则替换，否则插入到最前面
                    if state.messages and state.messages[0]["role"] == "system":
                        state.messages[0]["content"] = system_content
                    else:
                        state.messages.insert(0, {"role": "system", "content": system_content})
                    return True
                return False

            has_files = await _fetch_and_inject_files()
            if not has_files:
                if state.phase == AgentPhase.ERROR:
                    return
                state.phase = AgentPhase.WAIT_USER
                state.waiting_action = "need_file"
                event = await self._register_resume_event(state)
                await emit(
                    {
                        "type": "action_ask_user",
                        "message": "未检测到可用文件，请先上传文件。上传完成后点击\"已上传，继续\"。",
                        "payload": {"action": "need_file"},
                    }
                )
                try:
                    await asyncio.wait_for(event.wait(), timeout=300)
                except asyncio.TimeoutError:
                    await emit({"type": "error", "message": "等待用户响应超时，任务已终止"})
                    state.phase = AgentPhase.ERROR
                    return
                # 唤醒后重新获取文件列表
                has_files = await _fetch_and_inject_files()
                if not has_files:
                    await emit({"type": "error", "message": "仍未检测到文件，任务终止"})
                    state.phase = AgentPhase.ERROR
                    return

            state.phase = AgentPhase.EXECUTE
            for i in range(self.max_steps):
                if len(state.messages) > self.max_message_history:
                    system_msgs = [m for m in state.messages if m["role"] == "system"]
                    non_system = [m for m in state.messages if m["role"] != "system"]
                    keep = non_system[-(self.max_message_history - len(system_msgs)):]
                    state.messages = system_msgs + keep
                state.step_count += 1
                tools = self.tool_registry.list()
                decision = await self.llm.tool_call(state.messages, tools, context={"step": i + 1})
                await emit({"type": "action_progress", "message": f"Step {i + 1}: {decision.content}"})
                if decision.tool_name:
                    state.messages.append(
                        {
                            "role": "assistant",
                            "content": decision.content or None,
                            "tool_calls": [
                                {
                                    "id": f"call_{state.step_count}",
                                    "type": "function",
                                    "function": {
                                        "name": decision.tool_name,
                                        "arguments": decision.tool_arguments,
                                    },
                                }
                            ],
                        }
                    )
                else:
                    state.messages.append({"role": "assistant", "content": decision.content})

                if not decision.tool_name:
                    break

                try:
                    tool_args = json.loads(decision.tool_arguments) if decision.tool_arguments else {}
                except json.JSONDecodeError:
                    await emit({"type": "error", "message": f"LLM 返回的工具参数无法解析: {decision.tool_arguments}"})
                    break
                if not isinstance(tool_args, dict):
                    await emit({"type": "error", "message": "LLM 返回的工具参数必须为 JSON 对象"})
                    break

                try:
                    schema = self.tool_registry.get_schema(decision.tool_name)
                except KeyError:
                    await emit({"type": "error", "message": f"未知工具: {decision.tool_name}"})
                    break

                allowed_keys = set(schema.parameters.get("properties", {}).keys())
                filtered_args = {k: v for k, v in tool_args.items() if k in allowed_keys}
                required_keys = schema.parameters.get("required", [])
                missing = [key for key in required_keys if key not in filtered_args]
                if missing:
                    await emit({"type": "error", "message": f"工具参数缺失: {', '.join(missing)}"})
                    break

                result = await self.tool_registry.dispatch(
                    decision.tool_name,
                    user_id=state.user_id,
                    arguments=filtered_args,
                )
                MAX_TOOL_RESULT_CHARS = 6000
                if len(result) > MAX_TOOL_RESULT_CHARS:
                    result = result[:MAX_TOOL_RESULT_CHARS] + f"\n...(结果过长，已截断至 {MAX_TOOL_RESULT_CHARS} 字符)"
                state.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": f"call_{state.step_count}",
                        "content": result,
                    }
                )
            else:
                await emit({"type": "warning", "message": f"已达最大执行步数（{self.max_steps}），任务可能未完整完成，建议重新描述任务或拆分步骤。"})

            state.messages.append({"role": "user", "content": "请根据以上执行过程，给出简洁的任务完成总结。"})
            summary_result = await self.llm.tool_call(state.messages, [], context={"step": "summary"})
            summary = summary_result.content or "任务已完成。"
            # 把 summary 请求从 messages 里移除，避免污染后续对话
            state.messages.pop()
            await emit({"type": "message", "message": summary})
            state.phase = AgentPhase.DONE
            logger.info("Agent finished", extra={"session_id": state.session_id, "user_id": state.user_id})
        except Exception as e:
            state.phase = AgentPhase.ERROR
            logger.error("Agent failed", exc_info=e)
            raise
        finally:
            await self._pop_resume_event(state)

    async def resume(self, state: AgentState, action: str, value: str, emit: Emitter) -> None:
        if state.phase == AgentPhase.ERROR or state.phase in {AgentPhase.DONE}:
            await emit({"type": "message", "message": "任务已结束，无法恢复"})
            return
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
                self._resume_events.pop(key, None)
