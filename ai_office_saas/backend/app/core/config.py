"""全局配置模块：负责读取 config.yaml 并将配置对象缓存。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用基础配置。"""

    name: str = "AI Office SaaS"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


class SecurityConfig(BaseModel):
    """JWT 鉴权相关配置。"""

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120


class StorageConfig(BaseModel):
    """存储提供器配置。"""

    type: str = "local"
    base_path: str = "./data/users"


class LLMConfig(BaseModel):
    """大模型提供器配置。"""

    provider: str = "zhipu_mock"
    api_key: str = "mock-key"


class OfficeConfig(BaseModel):
    """办公 API 提供器配置。"""

    provider: str = "e5_mock"


class DatabaseConfig(BaseModel):
    """数据库配置。"""

    url: str = "sqlite:///./ai_office.db"


class Settings(BaseModel):
    """完整配置对象。"""

    app: AppConfig
    security: SecurityConfig
    storage: StorageConfig
    llm: LLMConfig
    office: OfficeConfig
    database: DatabaseConfig


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """读取并缓存配置文件，避免重复 IO。"""

    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    payload: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return Settings.model_validate(payload)
