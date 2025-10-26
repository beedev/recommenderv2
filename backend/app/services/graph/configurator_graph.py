"""
LangGraph Workflow for S1→S7 Configurator.

Agentic workflow with:
- Redis checkpointing for hot session data
- PostgreSQL archival for analytics
- LangSmith observability
- Multi-agent orchestration
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from langsmith import traceable

from ...models.graph_state import (
    ConfiguratorGraphState,
    AgentAction,
    Neo4jQuery,
    LLMExtraction,
    StateTransition
)
from ...models.conversation import ConfiguratorState
from ..intent.parameter_extractor import ParameterExtractor
from ..neo4j.product_search import ProductSearch
from ..response.message_generator import MessageGenerator

logger = logging.getLogger(__name__)


class ConfiguratorGraph:
    """
    LangGraph-based agentic workflow for S1→S7 configurator.

    Nodes:
    1. extract_parameters: LLM-based parameter extraction
    2. search_products: Neo4j product search
    3. generate_response: Conversational response
    4. determine_next_state: State transition logic
    """

    def __init__(
        self,
        parameter_extractor: ParameterExtractor,
        product_search: ProductSearch,
        message_generator: MessageGenerator,
        redis_checkpointer: RedisSaver
    ):
        """
        Initialize configurator graph with service dependencies.

        Args:
            parameter_extractor: LLM parameter extraction service
            product_search: Neo4j product search service
            message_generator: Response generation service
            redis_checkpointer: Redis checkpoint saver
        """
        self.parameter_extractor = parameter_extractor
        self.product_search = product_search
        self.message_generator = message_generator
        self.redis_checkpointer = redis_checkpointer

        # Build graph
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=redis_checkpointer)

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""

        workflow = StateGraph(ConfiguratorGraphState)

        # Add nodes
        workflow.add_node("extract_parameters", self.extract_parameters_node)
        workflow.add_node("search_products", self.search_products_node)
        workflow.add_node("generate_response", self.generate_response_node)
        workflow.add_node("determine_next_state", self.determine_next_state_node)

        # Define edges
        workflow.set_entry_point("extract_parameters")
        workflow.add_edge("extract_parameters", "search_products")
        workflow.add_edge("search_products", "generate_response")
        workflow.add_edge("generate_response", "determine_next_state")
        workflow.add_edge("determine_next_state", END)

        return workflow

    @traceable(name="extract_parameters", run_type="llm")
    async def extract_parameters_node(self, state: ConfiguratorGraphState) -> Dict[str, Any]:
        """
        Node 1: Extract parameters from user message using LLM.

        Uses GPT-4 to extract welding requirements into component-based structure.
        """
        start_time = time.time()

        try:
            logger.info(f"Extracting parameters for state: {state['current_state']}")

            # Call LLM parameter extraction
            updated_master = await self.parameter_extractor.extract_parameters(
                user_message=state["user_message"],
                current_state=state["current_state"],
                master_parameters=state["master_parameters"]
            )

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log extraction
            extraction = LLMExtraction(
                timestamp=datetime.utcnow().isoformat(),
                user_message=state["user_message"],
                current_state=state["current_state"],
                extracted_parameters=updated_master,
                model="gpt-4",
                tokens_used=0,  # TODO: Track from OpenAI response
                duration_ms=duration_ms,
                success=True,
                error=None
            )

            return {
                "master_parameters": updated_master,
                "llm_extractions": [extraction],
                "last_updated": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Parameter extraction failed: {e}")

            extraction = LLMExtraction(
                timestamp=datetime.utcnow().isoformat(),
                user_message=state["user_message"],
                current_state=state["current_state"],
                extracted_parameters={},
                model="gpt-4",
                tokens_used=0,
                duration_ms=int((time.time() - start_time) * 1000),
                success=False,
                error=str(e)
            )

            return {
                "llm_extractions": [extraction],
                "error": str(e),
                "retry_count": state.get("retry_count", 0) + 1
            }

    @traceable(name="search_products", run_type="retriever")
    async def search_products_node(self, state: ConfiguratorGraphState) -> Dict[str, Any]:
        """
        Node 2: Search Neo4j for matching products.

        Searches based on current state and extracted parameters.
        """
        start_time = time.time()

        try:
            component = state["current_state"].replace("_selection", "")
            logger.info(f"Searching products for component: {component}")

            # Get component-specific requirements
            component_params = state["master_parameters"].get(component, {})

            # Search Neo4j
            products = await self.product_search.search_by_component(
                component=component,
                requirements=component_params
            )

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log query
            query = Neo4jQuery(
                timestamp=datetime.utcnow().isoformat(),
                query_type="product_search",
                component=component,
                parameters=component_params,
                results_count=len(products),
                top_results=products[:3],
                duration_ms=duration_ms
            )

            return {
                "neo4j_queries": [query],
                "agent_actions": [AgentAction(
                    timestamp=datetime.utcnow().isoformat(),
                    agent_type="product_searcher",
                    action="search_by_component",
                    input={"component": component, "requirements": component_params},
                    output={"results_count": len(products), "top_results": products[:3]},
                    duration_ms=duration_ms,
                    success=True,
                    error=None
                )]
            }

        except Exception as e:
            logger.error(f"Product search failed: {e}")

            return {
                "agent_actions": [AgentAction(
                    timestamp=datetime.utcnow().isoformat(),
                    agent_type="product_searcher",
                    action="search_by_component",
                    input={"component": component},
                    output=None,
                    duration_ms=int((time.time() - start_time) * 1000),
                    success=False,
                    error=str(e)
                )],
                "error": str(e),
                "retry_count": state.get("retry_count", 0) + 1
            }

    @traceable(name="generate_response", run_type="llm")
    async def generate_response_node(self, state: ConfiguratorGraphState) -> Dict[str, Any]:
        """
        Node 3: Generate conversational response.

        Creates user-friendly response based on search results and state.
        """
        start_time = time.time()

        try:
            logger.info(f"Generating response for state: {state['current_state']}")

            # Generate response
            response_text = await self.message_generator.generate_message(
                current_state=ConfiguratorState(state["current_state"]),
                master_parameters=state["master_parameters"],
                response_json=state["response_json"]
            )

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "ai_response": response_text,
                "agent_actions": [AgentAction(
                    timestamp=datetime.utcnow().isoformat(),
                    agent_type="response_generator",
                    action="generate_message",
                    input={"current_state": state["current_state"]},
                    output={"response": response_text[:200]},  # Truncate for logging
                    duration_ms=duration_ms,
                    success=True,
                    error=None
                )]
            }

        except Exception as e:
            logger.error(f"Response generation failed: {e}")

            return {
                "ai_response": "I apologize, but I encountered an error. Could you please try again?",
                "agent_actions": [AgentAction(
                    timestamp=datetime.utcnow().isoformat(),
                    agent_type="response_generator",
                    action="generate_message",
                    input={"current_state": state["current_state"]},
                    output=None,
                    duration_ms=int((time.time() - start_time) * 1000),
                    success=False,
                    error=str(e)
                )],
                "error": str(e)
            }

    @traceable(name="determine_next_state", run_type="chain")
    async def determine_next_state_node(self, state: ConfiguratorGraphState) -> Dict[str, Any]:
        """
        Node 4: Determine next state based on applicability and user input.

        Implements S1→S7 state machine logic with auto-skip capability.
        """

        try:
            current_state = ConfiguratorState(state["current_state"])

            # Get next state based on applicability
            # TODO: Implement get_next_state logic from ConversationState
            # For now, simple progression
            state_order = [
                "power_source_selection",
                "feeder_selection",
                "cooler_selection",
                "interconnector_selection",
                "torch_selection",
                "accessories_selection",
                "finalize"
            ]

            current_idx = state_order.index(state["current_state"])
            next_state = state_order[current_idx + 1] if current_idx < len(state_order) - 1 else "finalize"

            # Log transition
            transition = StateTransition(
                timestamp=datetime.utcnow().isoformat(),
                from_state=state["current_state"],
                to_state=next_state,
                reason="progression",
                applicability_check=None
            )

            return {
                "next_state": next_state,
                "state_transitions": [transition],
                "checkpoint_count": state.get("checkpoint_count", 0) + 1,
                "last_updated": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"State transition failed: {e}")

            return {
                "error": str(e)
            }

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        current_state: ConfiguratorGraphState
    ) -> ConfiguratorGraphState:
        """
        Process user message through LangGraph workflow.

        Args:
            session_id: Session/thread ID for checkpointing
            user_message: User's natural language input
            current_state: Current graph state

        Returns:
            Updated graph state after workflow execution
        """

        # Update state with new message
        current_state["user_message"] = user_message
        current_state["messages"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Create config for checkpointing
        config = {"configurable": {"thread_id": session_id}}

        # Invoke graph with checkpointing
        result = await self.app.ainvoke(current_state, config)

        # Add AI response to messages
        result["messages"].append({
            "role": "assistant",
            "content": result.get("ai_response", ""),
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"Workflow completed. Checkpoint #{result.get('checkpoint_count', 0)} saved.")

        return result
