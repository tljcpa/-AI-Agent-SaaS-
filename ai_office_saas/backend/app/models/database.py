"""数据库模型与会话管理。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类。"""


engine = None
SessionLocal: sessionmaker | None = None


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


class UserFile(Base):
    """用户上传文件表。"""

    __tablename__ = "user_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    owner: Mapped[User] = relationship(back_populates="files")


def setup_database(database_url: str) -> None:
    """初始化数据库引擎与会话工厂（幂等）。"""

    global engine, SessionLocal
    if engine is not None and SessionLocal is not None:
        return

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _require_session_local() -> sessionmaker:
    if SessionLocal is None:
        raise RuntimeError("数据库尚未初始化，请先调用 init_db()")
    return SessionLocal


@contextmanager
def session_scope() -> Generator:
    """事务上下文管理器，确保异常时回滚。"""

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
    """初始化数据库表结构。"""
    settings = get_settings()
    setup_database(settings.database.url)
    if engine is None:
        raise RuntimeError("数据库引擎初始化失败")
    Base.metadata.create_all(bind=engine)
