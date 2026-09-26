"""Database connection engine and session management for OmniVox.

Supports:
- PostgreSQL (Aiven, Neon, Supabase, AWS RDS, self-hosted) with asyncpg / SSL
- SQLite fallback with aiosqlite for local development
- Async session dependency for FastAPI (`get_db`)
- Automatic table migration / initialization on startup (`init_db`)
"""
import logging
import os
from typing import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .. import config
from .models import Base

logger = logging.getLogger("omnivox.db")


def _format_async_db_url(raw_url: str | None) -> str:
    """Format raw database URL into an async-compatible driver URL (e.g. postgresql+asyncpg)."""
    if not raw_url:
        return "sqlite+aiosqlite:///omnivox.db"

    # If it's a standard PostgreSQL connection string
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("sqlite://") and not raw_url.startswith("sqlite+aiosqlite://"):
        raw_url = raw_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    # For asyncpg + sslmode=require (common in Aiven / cloud providers),
    # asyncpg expects 'ssl=require' or ssl context instead of sslmode
    if "postgresql+asyncpg://" in raw_url and "sslmode=" in raw_url:
        raw_url = raw_url.replace("sslmode=require", "ssl=require").replace("sslmode=prefer", "ssl=prefer")

    return raw_url


def _get_connect_args(url: str) -> dict:
    """Provide driver-specific connection arguments (e.g. SSL for cloud PostgreSQL)."""
    connect_args = {}
    if "postgresql+asyncpg" in url:
        if "ssl=require" in url or "aivencloud.com" in url:
            connect_args["ssl"] = "require"
    elif "sqlite" in url:
        connect_args["check_same_thread"] = False
    return connect_args


DB_URL = _format_async_db_url(config.DATABASE_URL)
_connect_args = _get_connect_args(DB_URL)

# Async engine for FastAPI endpoints
async_engine = create_async_engine(
    DB_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

# Async session factory
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an active async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize all database tables defined in models.py."""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"[db] Database tables initialized successfully ({DB_URL.split('@')[-1] if '@' in DB_URL else DB_URL})")
    except Exception as exc:
        print(f"[db] Database initialization warning / error: {exc}")
