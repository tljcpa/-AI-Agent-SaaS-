"""FastAPI 应用入口。"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
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
    app_env = os.getenv("APP_ENV", "development")

    docs_url = "/docs" if app_env == "development" else None
    redoc_url = "/redoc" if app_env == "development" else None
    openapi_url = "/openapi.json" if app_env == "development" else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0)
        ) as http_client:
            app.state.http_client = http_client
            app.state.container = build_container(settings, http_client)
            yield

    app = FastAPI(
        title=settings.app.name,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    app.state.limiter = auth.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

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
