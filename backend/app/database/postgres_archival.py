"""
PostgreSQL Archival Service for Completed Sessions.

Stores completed configurator sessions for:
- Long-term analytics
- Business intelligence
- Trend analysis
- Product recommendation tuning
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, String, JSON, DateTime, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import Base
from ..models.graph_state import ConfiguratorGraphState

logger = logging.getLogger(__name__)


class ArchivedSession(Base):
    """
    Archived session model for PostgreSQL.

    Stores completed configurator sessions with full conversation history
    and agent action logs for analytics.
    """

    __tablename__ = "archived_sessions"

    # Primary key
    session_id = Column(String(255), primary_key=True, index=True)

    # Session metadata
    created_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False)

    # Final state
    final_state = Column(String(100), nullable=False, index=True)
    finalized = Column(String(10), nullable=False)  # "yes" or "no"

    # User requirements (MasterParameterJSON)
    master_parameters = Column(JSON, nullable=False)

    # Selected products (ResponseJSON)
    response_json = Column(JSON, nullable=False)

    # Full conversation
    conversation_messages = Column(JSON, nullable=False)  # List of messages

    # Agent action logs
    agent_actions = Column(JSON, nullable=True)  # List of AgentAction
    neo4j_queries = Column(JSON, nullable=True)  # List of Neo4jQuery
    llm_extractions = Column(JSON, nullable=True)  # List of LLMExtraction
    state_transitions = Column(JSON, nullable=True)  # List of StateTransition

    # Summary for quick access
    total_messages = Column(Integer, nullable=False)
    total_agent_actions = Column(Integer, nullable=False)
    checkpoint_count = Column(Integer, nullable=False)

    # Error tracking
    had_errors = Column(String(10), nullable=False)  # "yes" or "no"
    error_log = Column(Text, nullable=True)


class PostgresArchivalService:
    """
    Service for archiving completed sessions to PostgreSQL.

    Provides:
    - Session archival from Redis
    - Analytics queries
    - Trend analysis
    """

    async def archive_session(
        self,
        session: AsyncSession,
        graph_state: ConfiguratorGraphState
    ):
        """
        Archive completed session to PostgreSQL.

        Args:
            session: SQLAlchemy async session
            graph_state: Completed configurator graph state
        """

        try:
            # Calculate duration
            created = datetime.fromisoformat(graph_state["created_at"])
            completed = datetime.utcnow()
            duration = int((completed - created).total_seconds())

            # Determine if finalized
            finalized = "yes" if graph_state["current_state"] == "finalize" else "no"

            # Check for errors
            had_errors = "yes" if graph_state.get("error") or graph_state.get("retry_count", 0) > 0 else "no"

            # Create archived session
            archived = ArchivedSession(
                session_id=graph_state["session_id"],
                created_at=created,
                completed_at=completed,
                duration_seconds=duration,
                final_state=graph_state["current_state"],
                finalized=finalized,
                master_parameters=graph_state["master_parameters"],
                response_json=graph_state["response_json"],
                conversation_messages=graph_state.get("messages", []),
                agent_actions=graph_state.get("agent_actions", []),
                neo4j_queries=graph_state.get("neo4j_queries", []),
                llm_extractions=graph_state.get("llm_extractions", []),
                state_transitions=graph_state.get("state_transitions", []),
                total_messages=len(graph_state.get("messages", [])),
                total_agent_actions=len(graph_state.get("agent_actions", [])),
                checkpoint_count=graph_state.get("checkpoint_count", 0),
                had_errors=had_errors,
                error_log=graph_state.get("error")
            )

            # Insert into database
            session.add(archived)
            await session.commit()

            logger.info(f"Archived session {graph_state['session_id']} to PostgreSQL")

        except Exception as e:
            logger.error(f"Failed to archive session: {e}")
            await session.rollback()
            raise

    async def get_session(
        self,
        session: AsyncSession,
        session_id: str
    ) -> Optional[ArchivedSession]:
        """
        Retrieve archived session by ID.

        Args:
            session: SQLAlchemy async session
            session_id: Session ID to retrieve

        Returns:
            Archived session or None
        """

        try:
            stmt = select(ArchivedSession).where(ArchivedSession.session_id == session_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            return None

    async def get_recent_sessions(
        self,
        session: AsyncSession,
        limit: int = 10
    ) -> List[ArchivedSession]:
        """
        Get most recent archived sessions.

        Args:
            session: SQLAlchemy async session
            limit: Number of sessions to retrieve

        Returns:
            List of recent sessions
        """

        try:
            stmt = (
                select(ArchivedSession)
                .order_by(ArchivedSession.completed_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Failed to retrieve recent sessions: {e}")
            return []

    async def get_analytics(
        self,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get analytics summary from archived sessions.

        Args:
            session: SQLAlchemy async session

        Returns:
            Analytics dictionary with metrics
        """

        try:
            # Count total sessions
            total_stmt = select(ArchivedSession)
            total_result = await session.execute(total_stmt)
            total_sessions = len(list(total_result.scalars().all()))

            # Count finalized sessions
            finalized_stmt = select(ArchivedSession).where(ArchivedSession.finalized == "yes")
            finalized_result = await session.execute(finalized_stmt)
            finalized_count = len(list(finalized_result.scalars().all()))

            # Count sessions with errors
            error_stmt = select(ArchivedSession).where(ArchivedSession.had_errors == "yes")
            error_result = await session.execute(error_stmt)
            error_count = len(list(error_result.scalars().all()))

            return {
                "total_sessions": total_sessions,
                "finalized_sessions": finalized_count,
                "finalization_rate": (finalized_count / total_sessions * 100) if total_sessions > 0 else 0,
                "error_sessions": error_count,
                "error_rate": (error_count / total_sessions * 100) if total_sessions > 0 else 0,
                "success_rate": ((total_sessions - error_count) / total_sessions * 100) if total_sessions > 0 else 0
            }

        except Exception as e:
            logger.error(f"Failed to get analytics: {e}")
            return {
                "total_sessions": 0,
                "finalized_sessions": 0,
                "finalization_rate": 0,
                "error_sessions": 0,
                "error_rate": 0,
                "success_rate": 0
            }


# Global service instance
postgres_archival_service = PostgresArchivalService()
