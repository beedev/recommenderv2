"""
Database configuration for Redis and PostgreSQL.

Redis: Hot session data with LangGraph checkpointing
PostgreSQL: Archival storage and analytics
"""

import logging
import os
from typing import AsyncGenerator, Optional
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for PostgreSQL models."""
    pass


class RedisManager:
    """
    Redis manager for hot session data and LangGraph checkpoints.

    Features:
    - Session state caching (24hr TTL)
    - LangGraph checkpoint storage
    - Async connection pooling
    """

    def __init__(self):
        """Initialize Redis manager with .env configuration."""
        self.redis_url = os.getenv("REDIS_URL")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.enable_caching = os.getenv("ENABLE_REDIS_CACHING", "true").lower() == "true"
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))

        self.client: Optional[Redis] = None
        self._initialized = False

    async def init_redis(self):
        """Initialize Redis connection."""
        if self._initialized:
            return

        try:
            # Use REDIS_URL if available, otherwise construct from components
            if self.redis_url:
                self.client = Redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    encoding="utf-8"
                )
            else:
                self.client = Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    decode_responses=True,
                    encoding="utf-8"
                )

            # Test connection
            await self.client.ping()
            self._initialized = True
            logger.info(f"Redis connected: {self.redis_host}:{self.redis_port}")

        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.client = None
            raise

    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")


class PostgreSQLManager:
    """
    PostgreSQL manager for archival storage and analytics.

    Features:
    - Session archival (permanent storage)
    - Analytics queries
    - Async SQLAlchemy session management
    """

    def __init__(self):
        """Initialize PostgreSQL manager with .env configuration."""
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB", "pconfig")
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "root")

        self.engine = None
        self.session_factory = None
        self._initialized = False

    def init_db(self):
        """Initialize PostgreSQL engine and session factory."""
        if self._initialized:
            return

        # Create async database URL
        database_url = (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

        # Create async engine
        self.engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging
            poolclass=NullPool,  # Use NullPool to avoid connection pool conflicts
            future=True
        )

        # Create session factory
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )

        self._initialized = True
        logger.info(f"PostgreSQL connected: {self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    async def close(self):
        """Close PostgreSQL engine."""
        if self.engine:
            await self.engine.dispose()
            logger.info("PostgreSQL engine disposed")


# Global manager instances
redis_manager = RedisManager()
postgresql_manager = PostgreSQLManager()


# Initialization functions
async def init_redis():
    """Initialize Redis connection."""
    await redis_manager.init_redis()


def init_postgresql():
    """Initialize PostgreSQL engine."""
    postgresql_manager.init_db()


# Dependency injection functions
async def get_redis_client() -> Redis:
    """
    Dependency for getting Redis client.

    Returns:
        Redis client instance
    """
    if not redis_manager._initialized:
        await redis_manager.init_redis()

    return redis_manager.client


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting PostgreSQL session.

    Yields:
        SQLAlchemy async session
    """
    if not postgresql_manager._initialized:
        postgresql_manager.init_db()

    async with postgresql_manager.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Cleanup functions
async def close_redis():
    """Close Redis connections."""
    await redis_manager.close()


async def close_postgresql():
    """Close PostgreSQL connections."""
    await postgresql_manager.close()
