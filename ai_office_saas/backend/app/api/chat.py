"""聊天 WebSocket：承载 Agent 事件流与人机协同。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from time import time
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.agent.engine import AgentEngine
from app.agent.state import AgentPhase, AgentState
from app.core.security import try_get_subject

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# 生产部署注意: 当前会话状态存储在进程内存中，仅支持单进程模式 (--workers=1)
# 如需多进程水平扩展，需将 session_states 迁移至 Redis
session_states: dict[str, AgentState] = {}
session_last_seen: dict[str, float] = {}
_session_lock = asyncio.Lock()
MAX_SESSION_STATES = 1000
SESSION_TTL_SECONDS = 60 * 60
_last_cleanup_time: float = 0.0
_CLEANUP_INTERVAL_SECONDS: float = 60.0

# 运行时兜底提示：检测到多 worker 时仅记录一次告警，避免刷日志。
_MULTI_WORKER_WARNING_LOGGED = False


async def _cleanup_session_states() -> None:
    global _last_cleanup_time
    now = time()
    if now - _last_cleanup_time < _CLEANUP_INTERVAL_SECONDS:
        return
    async with _session_lock:
        # 进锁后再次检查，避免多个协程同时通过节流判断后重复清理
        if now - _last_cleanup_time < _CLEANUP_INTERVAL_SECONDS:
            return
        expired = [sid for sid, last_seen in session_last_seen.items() if now - last_seen > SESSION_TTL_SECONDS]
        for sid in expired:
            session_last_seen.pop(sid, None)
            session_states.pop(sid, None)

        tracked_session_count = len(session_last_seen)
        if tracked_session_count > MAX_SESSION_STATES:
            overflow = tracked_session_count - MAX_SESSION_STATES
            oldest_session_ids = sorted(session_last_seen.items(), key=lambda item: item[1])[:overflow]
            for sid, _ in oldest_session_ids:
                session_last_seen.pop(sid, None)
                session_states.pop(sid, None)

        _last_cleanup_time = now


def get_agent_engine(websocket: WebSocket) -> AgentEngine:
    return websocket.app.state.container.agent_engine


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    # WebSocket 鉴权只支持 Authorization header 或首帧 auth 消息，不支持 query param 传 token。
    global _MULTI_WORKER_WARNING_LOGGED
    worker_count = int(os.environ.get("WEB_CONCURRENCY", "1"))
    if worker_count > 1 and not _MULTI_WORKER_WARNING_LOGGED:
        logger.warning(
            "WARNING: 检测到多 worker 模式，WebSocket 会话可能跨 worker 路由，请确认已配置 sticky session 或使用 --workers=1"
        )
        _MULTI_WORKER_WARNING_LOGGED = True

    await websocket.accept()

    token = websocket.headers.get("authorization", "").removeprefix("Bearer ").strip()
    session_id = websocket.query_params.get("session_id") or str(uuid4())
    await _cleanup_session_states()
    logger.info("WebSocket connected", extra={"session_id": session_id})

    state: AgentState | None = None
    engine = get_agent_engine(websocket)

    async def emit(payload: dict) -> None:
        await websocket.send_json({**payload, "session_id": session_id})

    await emit({"type": "message", "message": "连接成功，请输入任务描述。"})

    running_task: asyncio.Task | None = None
    try:
        while True:
            try:
                incoming_text = await websocket.receive_text()
                incoming = json.loads(incoming_text)
                if not isinstance(incoming, dict):
                    raise ValueError("payload must be object")
            except json.JSONDecodeError:
                if websocket.client_state != WebSocketState.CONNECTED:
                    return
                await emit({"type": "error", "message": "消息格式错误，请发送合法 JSON"})
                continue
            except ValueError:
                if websocket.client_state != WebSocketState.CONNECTED:
                    return
                await emit({"type": "error", "message": "消息格式错误，请发送合法 JSON"})
                continue
            except WebSocketDisconnect:
                raise
            except Exception:
                if websocket.client_state != WebSocketState.CONNECTED:
                    return
                await emit({"type": "error", "message": "消息格式错误，请发送合法 JSON"})
                continue

            kind = incoming.get("type")

            if state is None:
                if kind != "auth":
                    await emit({"type": "error", "message": "请先完成鉴权"})
                    await websocket.close(code=1008)
                    return

                auth_token = str(incoming.get("token", "")).strip() or token
                sub = try_get_subject(auth_token)
                if not sub or not sub.isdigit():
                    logger.warning("WebSocket auth failed", extra={"session_id": session_id})
                    await emit({"type": "error", "message": "鉴权失败"})
                    await websocket.close(code=1008)
                    return

                current_user_id = int(sub)
                async with _session_lock:
                    state = session_states.get(session_id)
                    if state is None:
                        state = AgentState(session_id=session_id, user_id=current_user_id)
                        session_states[session_id] = state
                    user_id_mismatch = state.user_id != current_user_id
                    if not user_id_mismatch:
                        session_last_seen[session_id] = time()

                if user_id_mismatch:
                    logger.warning(
                        "Possible cross-worker routing or session hijack detected",
                        extra={
                            "session_id": session_id,
                            "existing_user_id": state.user_id,
                            "current_user_id": current_user_id,
                        },
                    )
                    await emit({"type": "error", "message": "会话不属于当前用户"})
                    await websocket.close(code=1008)
                    return

                await emit({"type": "message", "message": "鉴权成功"})
                continue

            if kind == "start":
                async with _session_lock:
                    session_last_seen[session_id] = time()
                text = str(incoming.get("message", "")).strip()
                if not text:
                    await emit({"type": "error", "message": "任务描述不能为空"})
                    continue
                if running_task and not running_task.done():
                    await emit({"type": "error", "message": "当前已有任务在执行"})
                    continue

                def _on_task_done(task: asyncio.Task) -> None:
                    if task.cancelled():
                        return
                    exc = task.exception()
                    if exc:
                        logger.error("Agent task failed", exc_info=exc)

                state.task = ""
                state.messages = []
                state.step_count = 0
                state.phase = AgentPhase.IDLE
                state.waiting_action = None
                state.context = {}

                logger.info("Agent task started", extra={"session_id": session_id, "user_id": state.user_id})
                running_task = asyncio.create_task(engine.start(state, text, emit))
                running_task.add_done_callback(_on_task_done)

            elif kind == "user_action":
                if state is None:
                    await emit({"type": "error", "message": "请先完成鉴权"})
                    await websocket.close(code=1008)
                    return
                async with _session_lock:
                    session_last_seen[session_id] = time()
                action = str(incoming.get("action", "")).strip()
                value = str(incoming.get("value", "")).strip()
                if not action:
                    await emit({"type": "error", "message": "action 不能为空"})
                    continue
                await engine.resume(state, action, value, emit)

            else:
                await emit({"type": "error", "message": f"不支持的消息类型: {kind}"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", extra={"session_id": session_id})
        if running_task and not running_task.done():
            running_task.cancel()
        return
    except Exception as e:
        logger.error("WebSocket internal error", exc_info=e)
        try:
            await emit({"type": "error", "message": "服务端内部错误，请稍后重试或联系管理员"})
        except Exception:
            pass
