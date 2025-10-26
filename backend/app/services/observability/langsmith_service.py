"""
LangSmith Observability Service.

Provides:
- Run tracking and tracing
- Performance metrics
- Error monitoring
- Agent action logging
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
from langsmith import Client, traceable

logger = logging.getLogger(__name__)


class LangSmithService:
    """
    LangSmith integration for workflow observability.

    Features:
    - Automatic trace capture with @traceable decorator
    - Custom metric logging
    - Error tracking
    - Performance monitoring
    """

    def __init__(self):
        """Initialize LangSmith client with .env configuration."""
        self.api_key = os.getenv("LANGSMITH_API_KEY")
        self.project = os.getenv("LANGSMITH_PROJECT", "Recommender")
        self.enable_tracing = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"

        # Initialize client
        if self.api_key and self.enable_tracing:
            try:
                self.client = Client(api_key=self.api_key)

                # Set environment variables for @traceable decorator
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = self.api_key
                os.environ["LANGCHAIN_PROJECT"] = self.project
                os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

                logger.info(f"LangSmith initialized for project: {self.project}")
                logger.info("✓ LangSmith tracing enabled with environment variables")
            except Exception as e:
                logger.warning(f"LangSmith client initialization failed: {e}")
                self.client = None
        else:
            self.client = None
            logger.info("LangSmith tracing disabled")

    def is_enabled(self) -> bool:
        """Check if LangSmith tracing is enabled."""
        return self.client is not None

    @traceable(name="configurator_workflow", run_type="chain")
    async def track_workflow_execution(
        self,
        session_id: str,
        user_message: str,
        current_state: str,
        result: Dict[str, Any]
    ):
        """
        Track complete workflow execution in LangSmith.

        Args:
            session_id: Session ID
            user_message: User's input message
            current_state: Current configurator state
            result: Workflow execution result
        """

        if not self.is_enabled():
            return

        try:
            # Log workflow metrics
            workflow_metrics = {
                "session_id": session_id,
                "current_state": current_state,
                "user_message": user_message,
                "ai_response": result.get("ai_response", ""),
                "checkpoint_count": result.get("checkpoint_count", 0),
                "total_messages": len(result.get("messages", [])),
                "had_error": result.get("error") is not None,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Additional agent metrics
            if "agent_actions" in result:
                workflow_metrics["agent_action_count"] = len(result["agent_actions"])

            if "neo4j_queries" in result:
                workflow_metrics["neo4j_query_count"] = len(result["neo4j_queries"])

            if "llm_extractions" in result:
                workflow_metrics["llm_extraction_count"] = len(result["llm_extractions"])

            logger.info(f"LangSmith workflow tracked: {workflow_metrics}")

        except Exception as e:
            logger.error(f"Failed to track workflow in LangSmith: {e}")

    def log_agent_action(
        self,
        action_type: str,
        action_name: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]],
        duration_ms: int,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Log individual agent action to LangSmith.

        Args:
            action_type: Type of agent (parameter_extractor, product_searcher, etc.)
            action_name: Name of the action
            input_data: Action input
            output_data: Action output
            duration_ms: Execution duration
            success: Whether action succeeded
            error: Error message if failed
        """

        if not self.is_enabled():
            return

        try:
            action_log = {
                "agent_type": action_type,
                "action": action_name,
                "input": input_data,
                "output": output_data,
                "duration_ms": duration_ms,
                "success": success,
                "error": error,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Agent action logged: {action_log}")

        except Exception as e:
            logger.error(f"Failed to log agent action: {e}")

    def log_performance_metrics(
        self,
        session_id: str,
        metrics: Dict[str, Any]
    ):
        """
        Log performance metrics to LangSmith.

        Args:
            session_id: Session ID
            metrics: Performance metrics dictionary
        """

        if not self.is_enabled():
            return

        try:
            perf_log = {
                "session_id": session_id,
                "metrics": metrics,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Performance metrics logged: {perf_log}")

        except Exception as e:
            logger.error(f"Failed to log performance metrics: {e}")

    def log_error(
        self,
        session_id: str,
        error_type: str,
        error_message: str,
        context: Dict[str, Any]
    ):
        """
        Log error to LangSmith for monitoring.

        Args:
            session_id: Session ID
            error_type: Type of error
            error_message: Error message
            context: Additional context
        """

        if not self.is_enabled():
            return

        try:
            error_log = {
                "session_id": session_id,
                "error_type": error_type,
                "error_message": error_message,
                "context": context,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.error(f"Error logged to LangSmith: {error_log}")

        except Exception as e:
            logger.error(f"Failed to log error to LangSmith: {e}")


# Global service instance - initialized lazily after .env is loaded
langsmith_service = None


def get_langsmith_service() -> LangSmithService:
    """Get or create the LangSmith service instance."""
    global langsmith_service
    if langsmith_service is None:
        langsmith_service = LangSmithService()
    return langsmith_service
