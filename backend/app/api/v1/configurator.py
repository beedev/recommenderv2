"""
Configurator API Endpoint for S1→S7 Flow
POST /api/v1/configurator/message - Process user messages
POST /api/v1/configurator/select - Select a product
GET /api/v1/configurator/state - Get current state
"""

import logging
import uuid
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ...models.conversation import ConversationState, ConfiguratorState
from ...services.orchestrator.state_orchestrator import StateByStateOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/configurator", tags=["Configurator"])

# In-memory session storage (replace with Redis/DB for production)
sessions: Dict[str, ConversationState] = {}


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


def get_or_create_session(session_id: Optional[str] = None, reset: bool = False) -> ConversationState:
    """Get existing session or create new one"""

    if session_id and not reset and session_id in sessions:
        return sessions[session_id]

    # Create new session
    new_session_id = session_id or str(uuid.uuid4())
    conversation_state = ConversationState(session_id=new_session_id)
    sessions[new_session_id] = conversation_state

    logger.info(f"Created new session: {new_session_id}")
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
        # Get or create session
        conversation_state = get_or_create_session(request.session_id, request.reset)

        # Process message through orchestrator
        result = await orchestrator.process_message(conversation_state, request.message)

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
        # Get session
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        conversation_state = sessions[request.session_id]

        # Select product through orchestrator
        result = orchestrator.select_product(
            conversation_state,
            request.product_gin,
            request.product_data
        )

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
        # Get session
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        conversation_state = sessions[session_id]

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
    """Delete a session"""

    if session_id in sessions:
        del sessions[session_id]
        return {"message": "Session deleted", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail="Session not found")
