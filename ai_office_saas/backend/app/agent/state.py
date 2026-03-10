"""Agent 状态定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentPhase(str, Enum):
    """任务状态机阶段。"""

    IDLE = "idle"
    UNDERSTAND = "understand"
    PLAN = "plan"
    WAIT_USER = "wait_user"
    EXECUTE = "execute"
    DONE = "done"
    ERROR = "error"


@dataclass
class AgentState:
    """会话级 Agent 状态。"""

    session_id: str
    user_id: int
    task: str = ""
    phase: AgentPhase = AgentPhase.IDLE
    plan: list[str] = field(default_factory=list)
    current_step: int = 0
    waiting_action: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
