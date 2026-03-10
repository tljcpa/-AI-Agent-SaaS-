"""FastAPI 应用入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.llm_zhipu import ZhipuLLMProvider
from app.adapters.office_e5 import E5OfficeProvider
from app.adapters.storage_local import LocalStorageProvider
from app.agent.engine import AgentEngine
from app.api import auth, chat, files
from app.core.config import get_settings
from app.models.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app.name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 依赖注入装配：通过 config.yaml 选择具体实现。
    storage = LocalStorageProvider(base_path=settings.storage.base_path)
    llm = ZhipuLLMProvider(api_key=settings.llm.api_key)
    office = E5OfficeProvider()
    agent_engine = AgentEngine(llm=llm, storage=storage, office=office)

    files.router.storage_provider = storage
    chat.router.agent_engine = agent_engine

    app.include_router(auth.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()
