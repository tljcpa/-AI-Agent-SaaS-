"""FastAPI 应用入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, files, oauth
from app.core.config import get_settings
from app.core.container import build_container
from app.models.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        async with httpx.AsyncClient(timeout=30) as http_client:
            app.state.http_client = http_client
            app.state.container = build_container(settings, http_client)
            yield

    app = FastAPI(title=settings.app.name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(oauth.router, prefix="/api")

    return app


app = create_app()
