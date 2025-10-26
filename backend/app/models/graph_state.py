"""
LangGraph State Models for S1→S7 Agentic Workflow.

Bridges existing ConversationState with LangGraph's typed state system.
Enables agentic workflow with checkpointing and observability.
"""

from typing import TypedDict, Dict, List, Any, Optional, Annotated
from datetime import datetime
import operator

from .conversation import (
    ConversationState,
    ConfiguratorState,
    MasterParameterJSON,
    ResponseJSON
)


class ConfiguratorGraphState(TypedDict, total=False):
    """
    LangGraph state for S1→S7 configurator workflow.

    Extends ConversationState with LangGraph-specific fields for:
    - Agentic decision making
    - Checkpoint persistence
    - LangSmith observability
    """

    # Session identification
    session_id: str
    thread_id: str  # LangGraph thread ID for checkpointing

    # Current workflow state
    current_state: str  # ConfiguratorState enum value
    next_state: Optional[str]  # Proposed next state

    # User interaction
    user_message: str
    ai_response: str

    # Core JSON structures (from ConversationState)
    master_parameters: Dict[str, Any]  # MasterParameterJSON serialized
    response_json: Dict[str, Any]  # ResponseJSON serialized

    # Conversation history (append-only with operator.add)
    messages: Annotated[List[Dict[str, str]], operator.add]

    # Agentic workflow tracking
    agent_actions: Annotated[List[Dict[str, Any]], operator.add]  # Agent decision log
    neo4j_queries: Annotated[List[Dict[str, Any]], operator.add]  # Product search queries
    llm_extractions: Annotated[List[Dict[str, Any]], operator.add]  # Parameter extractions

    # State transitions
    state_transitions: Annotated[List[Dict[str, str]], operator.add]  # State change history

    # Metadata
    created_at: str  # ISO datetime
    last_updated: str  # ISO datetime
    checkpoint_count: int  # Number of checkpoints saved

    # Error handling
    error: Optional[str]
    retry_count: int


def conversation_state_to_graph_state(
    conv_state: ConversationState,
    user_message: str = "",
    ai_response: str = ""
) -> ConfiguratorGraphState:
    """
    Convert ConversationState to LangGraph ConfiguratorGraphState.

    Args:
        conv_state: Existing conversation state
        user_message: Current user message
        ai_response: Current AI response

    Returns:
        LangGraph-compatible state dict
    """

    return ConfiguratorGraphState(
        # Session IDs
        session_id=conv_state.session_id,
        thread_id=conv_state.session_id,  # Use same ID for simplicity

        # Current state
        current_state=conv_state.current_state.value,
        next_state=None,

        # Messages
        user_message=user_message,
        ai_response=ai_response,

        # Core JSON (convert Pydantic to dict)
        master_parameters=conv_state.master_parameters.dict(exclude={"last_updated"}),
        response_json=conv_state.response_json.dict(),

        # Conversation history
        messages=conv_state.conversation_history.copy(),

        # Agent tracking (initialize empty)
        agent_actions=[],
        neo4j_queries=[],
        llm_extractions=[],
        state_transitions=[],

        # Metadata
        created_at=conv_state.created_at.isoformat(),
        last_updated=conv_state.last_updated.isoformat(),
        checkpoint_count=0,

        # Error handling
        error=None,
        retry_count=0
    )


def graph_state_to_conversation_state(graph_state: ConfiguratorGraphState) -> ConversationState:
    """
    Convert LangGraph state back to ConversationState.

    Args:
        graph_state: LangGraph state dict

    Returns:
        ConversationState model
    """

    # Reconstruct master_parameters
    master_params = MasterParameterJSON(**graph_state["master_parameters"])

    # Reconstruct response_json
    response_json = ResponseJSON(**graph_state["response_json"])

    # Create conversation state
    conv_state = ConversationState(
        session_id=graph_state["session_id"],
        current_state=ConfiguratorState(graph_state["current_state"]),
        master_parameters=master_params,
        response_json=response_json,
        conversation_history=graph_state["messages"].copy(),
        created_at=datetime.fromisoformat(graph_state["created_at"]),
        last_updated=datetime.fromisoformat(graph_state["last_updated"])
    )

    return conv_state


class AgentAction(TypedDict):
    """
    Agent action log entry for observability.

    Tracks what the agent decided to do at each step.
    """

    timestamp: str  # ISO datetime
    agent_type: str  # "parameter_extractor", "product_searcher", "response_generator"
    action: str  # Action name
    input: Dict[str, Any]  # Action input
    output: Optional[Dict[str, Any]]  # Action output
    duration_ms: int  # Execution time
    success: bool
    error: Optional[str]


class Neo4jQuery(TypedDict):
    """
    Neo4j query log entry for observability.

    Tracks product searches and compatibility checks.
    """

    timestamp: str
    query_type: str  # "product_search", "compatibility_check"
    component: str  # Component being searched
    parameters: Dict[str, Any]  # Search parameters
    results_count: int
    top_results: List[Dict[str, Any]]  # Top 3 results
    duration_ms: int


class LLMExtraction(TypedDict):
    """
    LLM extraction log entry for observability.

    Tracks parameter extraction from user messages.
    """

    timestamp: str
    user_message: str
    current_state: str
    extracted_parameters: Dict[str, Any]  # Updated master_parameters
    model: str  # "gpt-4"
    tokens_used: int
    duration_ms: int
    success: bool
    error: Optional[str]


class StateTransition(TypedDict):
    """
    State transition log entry for workflow tracking.

    Tracks S1→S7 state progression.
    """

    timestamp: str
    from_state: str
    to_state: str
    reason: str  # "user_selection", "auto_skip", "applicability"
    applicability_check: Optional[Dict[str, str]]  # Component applicability flags
