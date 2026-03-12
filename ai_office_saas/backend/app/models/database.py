"""数据库模型与会话管理。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator
import threading

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类。"""


engine = None
SessionLocal: sessionmaker | None = None
_db_init_lock = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    files: Mapped[list[UserFile]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    oauth_tokens: Mapped[list[UserOAuthToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    oauth_states: Mapped[list[OAuthStateCache]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserFile(Base):
    """用户上传文件表。"""

    __tablename__ = "user_files"
    __table_args__ = (UniqueConstraint("user_id", "filename", name="uq_user_file"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    owner: Mapped[User] = relationship(back_populates="files")


class UserOAuthToken(Base):
    """用户 OAuth token（按 user_id 隔离）。"""

    __tablename__ = "user_oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="onedrive")
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_refreshing: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    user: Mapped[User] = relationship(back_populates="oauth_tokens")


class OAuthStateCache(Base):
    """OAuth state 一次性缓存，防止 CSRF。"""

    __tablename__ = "oauth_state_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    state_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="oauth_states")


def setup_database(database_url: str) -> None:
    global engine, SessionLocal
    with _db_init_lock:
        if engine is not None and SessionLocal is not None:
            return

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        engine = create_engine(database_url, connect_args=connect_args)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _require_session_local() -> sessionmaker:
    if SessionLocal is None:
        raise RuntimeError("数据库尚未初始化，请先调用 init_db()；请检查是否在 FastAPI lifespan 之前误调用了 session_scope()")
    return SessionLocal


@contextmanager
def session_scope() -> Generator:
    session = _require_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    # 注意：此函数必须且只能在 FastAPI lifespan 回调中调用。
    settings = get_settings()
    setup_database(settings.database.url)
    if engine is None:
        raise RuntimeError("数据库引擎初始化失败")
    Base.metadata.create_all(bind=engine)
