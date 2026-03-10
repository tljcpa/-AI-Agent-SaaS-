"""聊天 WebSocket：承载 Agent 事件流与人机协同。"""
from __future__ import annotations

import asyncio
from time import time
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent.engine import AgentEngine
from app.agent.state import AgentState
from app.core.security import try_get_subject

router = APIRouter(prefix="/chat", tags=["chat"])

# 会话态缓存：生产环境建议替换为 Redis。
session_states: dict[str, AgentState] = {}
session_last_seen: dict[str, float] = {}
MAX_SESSION_STATES = 1000
SESSION_TTL_SECONDS = 60 * 60


def _cleanup_session_states() -> None:
    now = time()
    expired = [sid for sid, last_seen in session_last_seen.items() if now - last_seen > SESSION_TTL_SECONDS]
    for sid in expired:
        session_last_seen.pop(sid, None)
        session_states.pop(sid, None)

    if len(session_states) <= MAX_SESSION_STATES:
        return

    oldest_session_ids = sorted(session_last_seen.items(), key=lambda item: item[1])[: len(session_states) - MAX_SESSION_STATES]
    for sid, _ in oldest_session_ids:
        session_last_seen.pop(sid, None)
        session_states.pop(sid, None)


def get_agent_engine(websocket: WebSocket) -> AgentEngine:
    return websocket.app.state.container.agent_engine


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    token = websocket.query_params.get("token", "")
    sub = try_get_subject(token)
    if not sub or not sub.isdigit():
        await websocket.send_json({"type": "error", "message": "鉴权失败"})
        await websocket.close(code=1008)
        return

    user_id = int(sub)
    session_id = websocket.query_params.get("session_id") or str(uuid4())
    _cleanup_session_states()

    state = session_states.get(session_id)
    if state is None:
        state = AgentState(session_id=session_id, user_id=user_id)
        session_states[session_id] = state
    elif state.user_id != user_id:
        await websocket.send_json({"type": "error", "message": "会话不属于当前用户"})
        await websocket.close(code=1008)
        return

    session_last_seen[session_id] = time()

    engine = get_agent_engine(websocket)

    async def emit(payload: dict) -> None:
        await websocket.send_json({**payload, "session_id": session_id})

    await emit({"type": "message", "message": "连接成功，请输入任务描述。"})

    running_task: asyncio.Task | None = None
    try:
        while True:
            incoming = await websocket.receive_json()
            kind = incoming.get("type")

            if kind == "start":
                session_last_seen[session_id] = time()
                text = str(incoming.get("message", "")).strip()
                if not text:
                    await emit({"type": "error", "message": "任务描述不能为空"})
                    continue
                if running_task and not running_task.done():
                    await emit({"type": "error", "message": "当前已有任务在执行"})
                    continue
                running_task = asyncio.create_task(engine.start(state, text, emit))

            elif kind == "user_action":
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
        return
