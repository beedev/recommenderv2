"""
Configurator API Endpoint for S1→S7 Flow
POST /api/v1/configurator/message - Process user messages
POST /api/v1/configurator/select - Select a product
GET /api/v1/configurator/state - Get current state
"""

import logging
import uuid
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ...models.conversation import ConversationState, ConfiguratorState
from ...services.orchestrator.state_orchestrator import StateByStateOrchestrator
from ...database.redis_session_storage import get_redis_session_storage
from ...database.postgres_archival import postgres_archival_service
from ...database.database import get_postgres_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/configurator", tags=["Configurator"])


class MessageRequest(BaseModel):
    """Request model for user message"""
    session_id: Optional[str] = None
    message: str
    reset: bool = False


class SelectProductRequest(BaseModel):
    """Request model for product selection"""
    session_id: str
    product_gin: str
    product_data: Dict


class MessageResponse(BaseModel):
    """Response model for message endpoint"""
    session_id: str
    message: str
    current_state: str
    master_parameters: Dict
    response_json: Dict
    products: Optional[list] = None
    awaiting_selection: bool = False
    can_finalize: bool = False


async def get_or_create_session(session_id: Optional[str] = None, reset: bool = False) -> ConversationState:
    """Get existing session from Redis or create new one"""

    redis_storage = get_redis_session_storage()

    if session_id and not reset:
        # Try to retrieve from Redis
        existing_session = await redis_storage.get_session(session_id)
        if existing_session:
            logger.info(f"Retrieved existing session from Redis: {session_id}")
            return existing_session

    # Create new session
    new_session_id = session_id or str(uuid.uuid4())
    conversation_state = ConversationState(session_id=new_session_id)

    # Save to Redis
    await redis_storage.save_session(conversation_state)

    logger.info(f"Created new session in Redis: {new_session_id}")
    return conversation_state


async def get_orchestrator_dep():
    """Dependency to get orchestrator - will be overridden in main.py"""
    pass


@router.post("/message", response_model=MessageResponse)
async def process_message(
    request: MessageRequest,
    orchestrator: StateByStateOrchestrator = Depends(get_orchestrator_dep)
):
    """
    Process user message in S1→S7 flow

    - Extracts parameters using LLM
    - Searches for compatible products
    - Generates conversational response
    - Manages state progression
    """

    try:
        redis_storage = get_redis_session_storage()

        # Get or create session from Redis
        conversation_state = await get_or_create_session(request.session_id, request.reset)

        # Process message through orchestrator
        result = await orchestrator.process_message(conversation_state, request.message)

        # Save updated session back to Redis
        await redis_storage.save_session(conversation_state)

        # Build response
        response = MessageResponse(
            session_id=conversation_state.session_id,
            message=result.get("message", ""),
            current_state=result.get("current_state", conversation_state.current_state.value),
            master_parameters=conversation_state.master_parameters.dict(),
            response_json=orchestrator._serialize_response_json(conversation_state),
            products=result.get("products", []),
            awaiting_selection=result.get("awaiting_selection", False),
            can_finalize=result.get("can_finalize", False)
        )

        return response

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/select")
async def select_product(
    request: SelectProductRequest,
    orchestrator: StateByStateOrchestrator = Depends(get_orchestrator_dep)
):
    """
    Select a product for current state component

    - Validates product selection
    - Updates response JSON
    - Moves to next state
    - Returns next state prompt
    """

    try:
        redis_storage = get_redis_session_storage()

        # Get session from Redis
        conversation_state = await redis_storage.get_session(request.session_id)
        if not conversation_state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Select product through orchestrator
        result = orchestrator.select_product(
            conversation_state,
            request.product_gin,
            request.product_data
        )

        # Save updated session back to Redis
        await redis_storage.save_session(conversation_state)

        # Build response
        response = MessageResponse(
            session_id=conversation_state.session_id,
            message=result.get("message", ""),
            current_state=result.get("current_state", conversation_state.current_state.value),
            master_parameters=conversation_state.master_parameters.dict(),
            response_json=orchestrator._serialize_response_json(conversation_state),
            products=[],
            awaiting_selection=False
        )

        return response

    except Exception as e:
        logger.error(f"Error selecting product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state/{session_id}")
async def get_state(
    session_id: str,
    orchestrator: StateByStateOrchestrator = Depends(get_orchestrator_dep)
):
    """
    Get current conversation state

    Returns:
        - Current state
        - Master parameters
        - Response JSON (selected products)
        - Conversation history
    """

    try:
        redis_storage = get_redis_session_storage()

        # Get session from Redis
        conversation_state = await redis_storage.get_session(session_id)
        if not conversation_state:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": conversation_state.session_id,
            "current_state": conversation_state.current_state.value,
            "master_parameters": conversation_state.master_parameters.dict(),
            "response_json": orchestrator._serialize_response_json(conversation_state),
            "conversation_history": conversation_state.conversation_history,
            "can_finalize": conversation_state.can_finalize()
        }

    except Exception as e:
        logger.error(f"Error getting state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session from Redis"""

    redis_storage = get_redis_session_storage()

    # Check if session exists
    exists = await redis_storage.session_exists(session_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete from Redis
    await redis_storage.delete_session(session_id)
    return {"message": "Session deleted", "session_id": session_id}


@router.post("/archive/{session_id}")
async def archive_session(
    session_id: str,
    postgres_session = Depends(get_postgres_session)
):
    """
    Archive completed session to PostgreSQL

    - Retrieves session from Redis
    - Converts to archival format
    - Stores in PostgreSQL
    - Optionally deletes from Redis
    """

    try:
        from datetime import datetime

        redis_storage = get_redis_session_storage()

        # Get session from Redis
        conversation_state = await redis_storage.get_session(session_id)
        if not conversation_state:
            raise HTTPException(status_code=404, detail="Session not found in Redis")

        # Recursive helper to serialize datetime objects to ISO strings
        def serialize_datetimes(obj):
            """Recursively convert datetime objects to ISO strings"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: serialize_datetimes(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_datetimes(item) for item in obj]
            return obj

        # Convert ConversationState to ConfiguratorGraphState format
        # Clean response_json - remove specifications dicts to avoid datetime serialization issues
        def clean_component(comp):
            if comp is None:
                return None
            comp_dict = comp.dict()
            # Remove specifications to avoid datetime serialization issues
            comp_dict.pop('specifications', None)
            return comp_dict

        graph_state = {
            "session_id": conversation_state.session_id,
            "current_state": conversation_state.current_state.value,
            "master_parameters": serialize_datetimes(conversation_state.master_parameters.dict()),
            "response_json": {
                "PowerSource": clean_component(conversation_state.response_json.PowerSource),
                "Feeder": clean_component(conversation_state.response_json.Feeder),
                "Cooler": clean_component(conversation_state.response_json.Cooler),
                "Interconnector": clean_component(conversation_state.response_json.Interconnector),
                "Torch": clean_component(conversation_state.response_json.Torch),
                "Accessories": [clean_component(acc) for acc in conversation_state.response_json.Accessories]
            },
            "messages": serialize_datetimes(conversation_state.conversation_history),
            "created_at": conversation_state.created_at.isoformat(),
            "agent_actions": [],
            "neo4j_queries": [],
            "llm_extractions": [],
            "state_transitions": [],
            "checkpoint_count": 0,
            "error": None,
            "retry_count": 0
        }

        # Archive to PostgreSQL
        await postgres_archival_service.archive_session(postgres_session, graph_state)

        return {
            "message": "Session archived successfully",
            "session_id": session_id,
            "archived_at": graph_state["created_at"]
        }

    except Exception as e:
        logger.error(f"Error archiving session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
