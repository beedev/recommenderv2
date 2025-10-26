"""
Database package for Recommender v2.

Provides Redis and PostgreSQL database management for:
- Redis: Hot session data with 24hr TTL
- PostgreSQL: Archival storage and analytics
"""

from .database import (
    RedisManager,
    PostgreSQLManager,
    redis_manager,
    postgresql_manager,
    init_redis,
    init_postgresql,
    get_redis_client,
    get_postgres_session,
    close_redis,
    close_postgresql
)

__all__ = [
    "RedisManager",
    "PostgreSQLManager",
    "redis_manager",
    "postgresql_manager",
    "init_redis",
    "init_postgresql",
    "get_redis_client",
    "get_postgres_session",
    "close_redis",
    "close_postgresql"
]
