"""
LangGraph Wrapper for StateByStateOrchestrator
Provides LangGraph observability without disrupting existing functionality
Delegates all orchestration to StateByStateOrchestrator
"""

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langsmith import traceable

from ...models.graph_state import ConfiguratorGraphState
from ...models.conversation import ConversationState
from ..orchestrator.state_orchestrator import StateByStateOrchestrator

logger = logging.getLogger(__name__)


class ConfiguratorGraphWrapper:
    """
    Lightweight LangGraph wrapper for StateByStateOrchestrator

    Benefits:
    - LangGraph workflow visualization in LangSmith
    - Checkpointing support for workflow state
    - Graph-based observability without code changes
    - Delegates all business logic to existing orchestrator
    """

    def __init__(self, orchestrator: StateByStateOrchestrator):
        """
        Initialize wrapper with existing orchestrator

        Args:
            orchestrator: Existing StateByStateOrchestrator instance
        """
        self.orchestrator = orchestrator
        self.graph = self._build_graph()
        self.app = self.graph.compile()
        logger.info("LangGraph wrapper initialized - delegating to StateByStateOrchestrator")

    def _build_graph(self) -> StateGraph:
        """Build minimal LangGraph workflow that delegates to orchestrator"""

        workflow = StateGraph(ConfiguratorGraphState)

        # Single node that wraps orchestrator.process_message()
        workflow.add_node("process_message", self.process_message_node)

        # Simple flow: entry → process → end
        workflow.set_entry_point("process_message")
        workflow.add_edge("process_message", END)

        return workflow

    @traceable(name="langgraph_process_message", run_type="chain")
    async def process_message_node(self, state: ConfiguratorGraphState) -> Dict[str, Any]:
        """
        LangGraph node that delegates to StateByStateOrchestrator

        This node wraps the orchestrator's process_message() method,
        providing LangGraph observability without changing logic.
        """
        try:
            # Convert ConfiguratorGraphState to ConversationState
            conversation_state = self._graph_state_to_conversation_state(state)

            # Extract user message from state
            user_message = state.get("messages", [])[-1] if state.get("messages") else ""

            # Delegate to existing orchestrator
            result = await self.orchestrator.process_message(conversation_state, user_message)

            # Update graph state with result
            updated_state = {
                "master_parameters": conversation_state.master_parameters.dict(),
                "response_json": self._serialize_response_json(conversation_state),
                "current_state": conversation_state.current_state.value,
                "messages": state.get("messages", []) + [result.get("message", "")]
            }

            logger.info(f"LangGraph node completed - state: {conversation_state.current_state.value}")
            return updated_state

        except Exception as e:
            logger.error(f"LangGraph node error: {e}", exc_info=True)
            return {
                "error": str(e),
                "retry_count": state.get("retry_count", 0) + 1
            }

    @traceable(name="langgraph_select_product", run_type="chain")
    async def select_product_node(self, state: ConfiguratorGraphState) -> Dict[str, Any]:
        """
        LangGraph node for product selection
        Delegates to orchestrator.select_product()
        """
        try:
            conversation_state = self._graph_state_to_conversation_state(state)

            # Extract product selection data from state
            product_gin = state.get("selected_product_gin", "")
            product_data = state.get("selected_product_data", {})

            # Delegate to existing orchestrator
            result = await self.orchestrator.select_product(
                conversation_state,
                product_gin,
                product_data
            )

            # Update graph state
            updated_state = {
                "master_parameters": conversation_state.master_parameters.dict(),
                "response_json": self._serialize_response_json(conversation_state),
                "current_state": conversation_state.current_state.value,
                "messages": state.get("messages", []) + [result.get("message", "")]
            }

            logger.info(f"LangGraph product selection completed - state: {conversation_state.current_state.value}")
            return updated_state

        except Exception as e:
            logger.error(f"LangGraph product selection error: {e}", exc_info=True)
            return {
                "error": str(e),
                "retry_count": state.get("retry_count", 0) + 1
            }

    def _graph_state_to_conversation_state(self, graph_state: ConfiguratorGraphState) -> ConversationState:
        """Convert ConfiguratorGraphState to ConversationState"""
        from ...models.conversation import MasterParameterJSON, ResponseJSON
        from ...models.conversation import ConfiguratorState as ConvState

        # Create ConversationState from graph state
        conversation_state = ConversationState(
            session_id=graph_state.get("session_id", ""),
            language=graph_state.get("language", "en")
        )

        # Restore state from graph
        if graph_state.get("current_state"):
            conversation_state.current_state = ConvState(graph_state["current_state"])

        if graph_state.get("master_parameters"):
            conversation_state.master_parameters = MasterParameterJSON(**graph_state["master_parameters"])

        if graph_state.get("response_json"):
            response_data = graph_state["response_json"]
            conversation_state.response_json = ResponseJSON(
                PowerSource=response_data.get("PowerSource"),
                Feeder=response_data.get("Feeder"),
                Cooler=response_data.get("Cooler"),
                Interconnector=response_data.get("Interconnector"),
                Torch=response_data.get("Torch"),
                Accessories=response_data.get("Accessories", [])
            )

        if graph_state.get("messages"):
            conversation_state.conversation_history = graph_state["messages"]

        return conversation_state

    def _serialize_response_json(self, conversation_state: ConversationState) -> Dict:
        """Serialize ResponseJSON for graph state"""
        return {
            "PowerSource": conversation_state.response_json.PowerSource.dict() if conversation_state.response_json.PowerSource else None,
            "Feeder": conversation_state.response_json.Feeder.dict() if conversation_state.response_json.Feeder else None,
            "Cooler": conversation_state.response_json.Cooler.dict() if conversation_state.response_json.Cooler else None,
            "Interconnector": conversation_state.response_json.Interconnector.dict() if conversation_state.response_json.Interconnector else None,
            "Torch": conversation_state.response_json.Torch.dict() if conversation_state.response_json.Torch else None,
            "Accessories": [acc.dict() for acc in conversation_state.response_json.Accessories]
        }

    async def invoke(self, session_id: str, user_message: str, language: str = "en") -> Dict[str, Any]:
        """
        Invoke LangGraph workflow

        Args:
            session_id: Session identifier
            user_message: User's message
            language: Language code

        Returns:
            Workflow result with orchestrator response
        """
        initial_state = {
            "session_id": session_id,
            "current_state": "power_source_selection",
            "master_parameters": {},
            "response_json": {},
            "messages": [user_message],
            "language": language,
            "agent_actions": [],
            "neo4j_queries": [],
            "llm_extractions": [],
            "state_transitions": [],
            "checkpoint_count": 0,
            "error": None,
            "retry_count": 0
        }

        result = await self.app.ainvoke(initial_state)
        logger.info(f"LangGraph workflow completed for session: {session_id}")
        return result
