"""全局配置模块：负责读取 config.yaml 并将配置对象缓存。"""
from __future__ import annotations

from functools import lru_cache
import os
from os import getenv
from pathlib import Path
from typing import Any
import warnings

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "AI Office SaaS"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    agent_max_steps: int = 5


class SecurityConfig(BaseModel):
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120


class StorageConfig(BaseModel):
    type: str = "local"
    base_path: str = "./data/users"
    onedrive_root: str = "/"


class LLMConfig(BaseModel):
    provider: str = "zhipu_mock"
    api_key: str = "mock-key"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"


class OfficeConfig(BaseModel):
    provider: str = "e5_mock"


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./ai_office.db"


class MSGraphConfig(BaseModel):
    tenant_id: str = "common"
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8000/api/oauth/callback"
    scopes: list[str] = Field(default_factory=lambda: ["Files.ReadWrite", "offline_access"])


class Settings(BaseModel):
    app: AppConfig
    security: SecurityConfig
    storage: StorageConfig
    llm: LLMConfig
    office: OfficeConfig
    database: DatabaseConfig
    ms_graph: MSGraphConfig = Field(default_factory=MSGraphConfig)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """读取并缓存配置；开发模式下修改 config.yaml 后需调用 reset_settings_cache() 刷新。"""

    base_dir = Path(__file__).resolve().parents[2]
    config_path = base_dir / "config.yaml"
    if not config_path.exists():
        config_path = base_dir / "config.yaml.example"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {base_dir / 'config.yaml'}")

    payload: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    env_jwt_secret = getenv("JWT_SECRET")
    if env_jwt_secret:
        payload.setdefault("security", {})["jwt_secret"] = env_jwt_secret

    # 生产部署改造：支持通过环境变量覆盖关键配置，避免明文写入配置文件。
    if os.getenv("LLM_API_KEY"):
        payload.setdefault("llm", {})["api_key"] = os.getenv("LLM_API_KEY")
    if os.getenv("DB_URL"):
        payload.setdefault("database", {})["url"] = os.getenv("DB_URL")
    if os.getenv("FRONTEND_ORIGIN"):
        payload.setdefault("app", {})["cors_origins"] = [os.getenv("FRONTEND_ORIGIN")]

    settings = Settings.model_validate(payload)
    app_env = getenv("APP_ENV", "development")
    jwt_secret_bytes_len = len(settings.security.jwt_secret.encode("utf-8"))
    if jwt_secret_bytes_len < 32:
        if app_env == "production":
            raise RuntimeError("jwt_secret 强度不足，生产环境要求至少 32 字节")
        warnings.warn("jwt_secret 强度不足，建议至少使用 32 字节随机密钥", stacklevel=2)

    if settings.security.jwt_secret == "INSECURE_DEV_ONLY_SET_JWT_SECRET_ENV" and app_env != "development":
        raise RuntimeError("生产环境必须通过 JWT_SECRET 环境变量设置强密钥")
    return settings


def reset_settings_cache() -> None:
    """供开发模式热更新时清空 lru_cache。"""

    get_settings.cache_clear()
