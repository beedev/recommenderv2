# LLM-Driven Entity Extraction Architecture

**Version**: 1.0
**Date**: 2025-10-24
**Status**: Architecture Design - LLM Prompt-Based Extraction

---

## Executive Summary

The LLM directly fills the Master Parameter JSON through structured prompts, not through code-based extraction. This approach:
- ✅ Leverages LLM's semantic understanding
- ✅ Handles ambiguity and clarification naturally
- ✅ Normalizes values according to spec standards
- ✅ Produces deterministic, structured output

**Spec Reference**: Section 7 - LLM Semantic Extraction (Lines 597-695)

---

## 1. Architecture Overview

### 1.1 LLM Extraction Flow

```
User Message
    ↓
[System Prompt] → Instructions for entity extraction and normalization
    ↓
[User Prompt] → Current Master JSON + New user message + Extraction rules
    ↓
[Claude LLM] → Parse, normalize, extract entities
    ↓
[Structured JSON Output] → Updated Master Parameter JSON
    ↓
[Validation] → Pydantic models validate and ensure correctness
    ↓
[Session Storage] → Save updated Master JSON to conversation session
```

### 1.2 Key Components

1. **System Prompt**: Instructions for entity extraction behavior
2. **User Prompt Template**: Structured template with current state + new input
3. **Output Schema**: JSON schema that LLM must follow
4. **Validation Layer**: Pydantic models enforce correctness
5. **Clarification Handler**: Detect when LLM needs user clarification

---

## 2. LLM Prompt Engineering

### 2.1 System Prompt

**Location**: `/backend/app/services/extraction/prompts/entity_extraction_system.txt`

```
You are an expert welding equipment configurator assistant. Your job is to extract and normalize welding equipment parameters from user messages.

## Your Responsibilities

1. **Parse User Intent**: Understand what welding equipment parameters the user is specifying
2. **Extract Entities**: Identify specific attributes for each component (PowerSource, Feeder, Cooler, Interconnect, Torch)
3. **Normalize Values**: Convert all values to standardized formats according to the normalization rules
4. **Detect Products**: Recognize specific product names and models (e.g., "Aristo 500ix", "Python 450")
5. **Handle Ambiguity**: When unclear, mark fields for clarification

## Normalization Rules (CRITICAL - ALWAYS FOLLOW)

### Current Output / Amperage
- Format: "XXX A" (with space, capital A)
- Examples: "500" → "500 A", "300 amps" → "300 A", "half kilowatt" → "500 A"

### Voltage
- Format: "XXXV" (no space, capital V)
- Examples: "220 volts" → "220V", "460v" → "460V", "230" → "230V"

### Phase
- Format: "single-phase" or "3-phase"
- Examples: "3 phase" → "3-phase", "three phase" → "3-phase", "1 phase" → "single-phase"

### Welding Process
- Format: "ProcessName (Abbreviation)"
- Options:
  - "MIG (GMAW)"
  - "TIG (GTAW)"
  - "Stick (SMAW)"
  - "Flux-Cored (FCAW)"
  - "Submerged Arc (SAW)"
- Examples: "MIG" → "MIG (GMAW)", "TIG welding" → "TIG (GTAW)"

### Cooling Type
- Format: lowercase
- Options: "water", "air", "none"
- Examples: "water-cooled" → "water", "air cooling" → "air"

### Wire Size
- Format: "X.XXX inch" (with leading zero for decimals)
- Examples: ".035" → "0.035 inch", "035 wire" → "0.035 inch", "0.045" → "0.045 inch"

### Cable Length
- Format: "XX ft" (feet)
- Examples: "25 feet" → "25 ft", "50'" → "50 ft", "10 meters" → "33 ft"

### Material
- Format: lowercase
- Examples: "Aluminum" → "aluminum", "Stainless Steel" → "stainless steel"

### Portability
- Format: lowercase
- Options: "portable", "stationary"

## Component Categories

### PowerSource Parameters
- process: Welding process
- current_output: Amperage rating
- duty_cycle: Duty cycle percentage
- material: Material to weld
- phase: Electrical phase
- voltage: Input voltage

### Feeder Parameters
- process: Welding process
- portability: Portable or stationary
- wire_size: Wire diameter
- material: Wire material

### Cooler Parameters
- cooling_type: Type of cooling (water/air/none)
- flow_rate: Flow rate (e.g., "2 GPM")
- capacity: Tank capacity (e.g., "3 gallon")

### Interconnect Parameters
- type: Cable type
- length: Cable length
- connector_type: Connector specification

### Torch Parameters
- process: Welding process
- cooling_type: Torch cooling type
- material: Handle material
- amperage_rating: Torch amperage capacity

## Direct Product Recognition

When user mentions specific product names, extract them exactly:
- "Aristo 500ix" → PowerSource direct_product_mention
- "Renegade ES300" → PowerSource direct_product_mention
- "Python 450" → Feeder direct_product_mention
- "Bernard Q400" → Torch direct_product_mention
- etc.

## Update Behavior

1. **Latest Value Wins**: If user provides new value for existing parameter, OVERWRITE the old value
2. **Never Delete**: Only update parameters user mentions, leave others unchanged
3. **Multi-Component**: User may specify parameters for multiple components in one message
4. **Clarification**: If ambiguous, set needs_clarification=true and provide clarification_question

## Output Format

You MUST respond with valid JSON matching this exact schema:

{
  "master_json_updates": {
    "PowerSource": {
      "process": "",
      "current_output": "",
      "duty_cycle": "",
      "material": "",
      "phase": "",
      "voltage": "",
      "direct_product_mention": ""
    },
    "Feeder": {
      "process": "",
      "portability": "",
      "wire_size": "",
      "material": "",
      "direct_product_mention": ""
    },
    "Cooler": {
      "cooling_type": "",
      "flow_rate": "",
      "capacity": "",
      "direct_product_mention": ""
    },
    "Interconnect": {
      "type": "",
      "length": "",
      "connector_type": "",
      "direct_product_mention": ""
    },
    "Torch": {
      "process": "",
      "cooling_type": "",
      "material": "",
      "amperage_rating": "",
      "direct_product_mention": ""
    }
  },
  "needs_clarification": false,
  "clarification_question": "",
  "confidence_scores": {
    "PowerSource": 0.0,
    "Feeder": 0.0,
    "Cooler": 0.0,
    "Interconnect": 0.0,
    "Torch": 0.0
  },
  "reasoning": ""
}

IMPORTANT: Only include components in master_json_updates that have at least ONE non-empty parameter. Omit components with all empty values.
```

---

### 2.2 User Prompt Template

**Location**: `/backend/app/services/extraction/prompts/entity_extraction_user_template.txt`

```
## Current Master Parameter JSON

Here is the current state of extracted parameters from previous conversation:

{current_master_json}

## New User Message

The user just said:
"{user_message}"

## Conversation Context

Current conversation state: {current_state}
Previous user messages: {conversation_history}

## Your Task

1. Analyze the new user message
2. Extract any welding equipment parameters mentioned
3. Normalize all values according to the normalization rules
4. Update ONLY the parameters mentioned by the user (keep existing parameters unchanged unless user explicitly changes them)
5. If user mentions a specific product name, extract it to direct_product_mention
6. If anything is ambiguous or unclear, set needs_clarification=true

Remember:
- Latest value wins (user can change their mind)
- Normalize ALL values to spec format
- Only update parameters user mentions
- Provide confidence scores (0.0 to 1.0)
- Explain your reasoning

Respond with the JSON output schema.
```

---

## 3. Implementation

### 3.1 LLM Entity Extraction Service

**Location**: `/backend/app/services/extraction/llm_entity_extractor.py`

```python
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic
import json
import logging
from pathlib import Path
from pydantic import BaseModel, Field

from ...models.master_parameter import MasterParameterJSON
from ...models.conversation_models import ConversationState

logger = logging.getLogger(__name__)


class LLMExtractionOutput(BaseModel):
    """Structured output from LLM entity extraction"""

    master_json_updates: Dict[str, Dict[str, Any]]
    needs_clarification: bool = False
    clarification_question: str = ""
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    reasoning: str = ""


class LLMEntityExtractor:
    """
    Uses Claude LLM to extract and normalize entities from user messages

    Implements Spec Section 7: LLM Semantic Extraction
    """

    def __init__(self, anthropic_api_key: str):
        self.client = AsyncAnthropic(api_key=anthropic_api_key)
        self.model = "claude-3-5-sonnet-20241022"

        # Load prompts
        prompts_dir = Path(__file__).parent / "prompts"

        with open(prompts_dir / "entity_extraction_system.txt", "r") as f:
            self.system_prompt = f.read()

        with open(prompts_dir / "entity_extraction_user_template.txt", "r") as f:
            self.user_prompt_template = f.read()

    async def extract_entities(
        self,
        user_message: str,
        current_master_json: MasterParameterJSON,
        current_state: ConversationState,
        conversation_history: List[str]
    ) -> LLMExtractionOutput:
        """
        Extract entities from user message using Claude LLM

        Args:
            user_message: Latest user message
            current_master_json: Current Master Parameter JSON state
            current_state: Current conversation state
            conversation_history: Recent user messages for context

        Returns:
            LLMExtractionOutput with updates and metadata
        """

        # Format current Master JSON for prompt
        current_json_str = json.dumps(
            current_master_json.to_dict(),
            indent=2
        )

        # Format conversation history (last 3 messages)
        history_str = "\n".join([f"- {msg}" for msg in conversation_history[-3:]])

        # Build user prompt
        user_prompt = self.user_prompt_template.format(
            current_master_json=current_json_str,
            user_message=user_message,
            current_state=current_state.value,
            conversation_history=history_str if history_str else "No previous messages"
        )

        try:
            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.0  # Deterministic output
            )

            # Extract JSON from response
            response_text = response.content[0].text

            # Parse JSON (handle markdown code blocks)
            json_text = self._extract_json_from_response(response_text)
            extraction_output = json.loads(json_text)

            # Validate and return
            return LLMExtractionOutput(**extraction_output)

        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}")

            # Return empty extraction on error
            return LLMExtractionOutput(
                master_json_updates={},
                needs_clarification=True,
                clarification_question="I had trouble understanding that. Could you rephrase?",
                confidence_scores={},
                reasoning=f"Extraction error: {str(e)}"
            )

    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from LLM response (handles markdown code blocks)"""

        # Check for markdown code block
        if "```json" in response_text:
            # Extract content between ```json and ```
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            return response_text[start:end].strip()

        elif "```" in response_text:
            # Extract content between ``` and ```
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            return response_text[start:end].strip()

        else:
            # Assume entire response is JSON
            return response_text.strip()

    def apply_updates_to_master_json(
        self,
        extraction_output: LLMExtractionOutput,
        master_json: MasterParameterJSON
    ) -> MasterParameterJSON:
        """
        Apply LLM extraction updates to Master Parameter JSON

        Implements "latest value wins" logic
        """

        for component, updates in extraction_output.master_json_updates.items():
            if component in ["PowerSource", "Feeder", "Cooler", "Interconnect", "Torch"]:
                # Filter out empty values
                non_empty_updates = {
                    k: v for k, v in updates.items()
                    if v and v != ""
                }

                if non_empty_updates:
                    # Update component parameters
                    master_json.update_component(component, non_empty_updates)
                    logger.info(f"Updated {component}: {non_empty_updates}")

        return master_json


def get_llm_entity_extractor(api_key: str) -> LLMEntityExtractor:
    """Get LLM entity extractor instance"""
    return LLMEntityExtractor(api_key)
```

---

### 3.2 Integration with Conversational Manager

**Modify**: `/backend/app/services/enterprise/conversational_manager.py`

```python
from ..extraction.llm_entity_extractor import get_llm_entity_extractor
import os

class ConversationalManager:

    def __init__(self, intent_service, neo4j_service):
        # ... existing initialization ...

        # Initialize LLM entity extractor
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm_extractor = get_llm_entity_extractor(anthropic_api_key)

    async def _process_turn(self, session, user_message):
        """Process conversation turn with LLM entity extraction"""

        # Get conversation history for context
        recent_messages = [
            turn.message for turn in session.turns[-5:]
            if turn.role == "user"
        ]

        # EXTRACT ENTITIES USING LLM
        extraction_result = await self.llm_extractor.extract_entities(
            user_message=user_message,
            current_master_json=session.master_parameters,
            current_state=session.current_state,
            conversation_history=recent_messages
        )

        # Log extraction results
        logger.info(f"LLM Extraction - Reasoning: {extraction_result.reasoning}")
        logger.info(f"LLM Extraction - Confidence: {extraction_result.confidence_scores}")

        # CHECK FOR CLARIFICATION NEEDED
        if extraction_result.needs_clarification:
            # Return clarification question to user
            return extraction_result.clarification_question, [], session.current_state

        # APPLY UPDATES TO MASTER JSON
        session.master_parameters = self.llm_extractor.apply_updates_to_master_json(
            extraction_result,
            session.master_parameters
        )

        # Log updated Master JSON
        logger.info(f"Master Parameters: {session.master_parameters.to_dict()}")

        # Continue with existing state machine logic...
```

---

## 4. Example Interactions

### 4.1 Example 1: Simple Parameter Extraction

**User Message**: "I need 500 amps for MIG welding"

**LLM Input**:
```json
{
  "current_master_json": {
    "PowerSource": {},
    "Feeder": {},
    ...
  },
  "user_message": "I need 500 amps for MIG welding"
}
```

**LLM Output**:
```json
{
  "master_json_updates": {
    "PowerSource": {
      "current_output": "500 A",
      "process": "MIG (GMAW)"
    }
  },
  "needs_clarification": false,
  "clarification_question": "",
  "confidence_scores": {
    "PowerSource": 0.95
  },
  "reasoning": "User specified 500 amps current output and MIG welding process. Normalized '500 amps' to '500 A' and 'MIG' to 'MIG (GMAW)' per spec."
}
```

---

### 4.2 Example 2: Direct Product Mention

**User Message**: "I want an Aristo 500ix power source"

**LLM Output**:
```json
{
  "master_json_updates": {
    "PowerSource": {
      "direct_product_mention": "Aristo 500ix"
    }
  },
  "needs_clarification": false,
  "clarification_question": "",
  "confidence_scores": {
    "PowerSource": 1.0
  },
  "reasoning": "User mentioned specific product 'Aristo 500ix'. This will trigger direct GIN lookup in Neo4j, which will then enrich the Master JSON with product attributes."
}
```

---

### 4.3 Example 3: User Changes Mind

**Turn 1 User**: "500 amps"

**LLM Output**:
```json
{
  "master_json_updates": {
    "PowerSource": {
      "current_output": "500 A"
    }
  }
}
```

**Turn 2 User**: "Actually, make it 300 amps"

**Current Master JSON**:
```json
{
  "PowerSource": {
    "current_output": "500 A"
  }
}
```

**LLM Output**:
```json
{
  "master_json_updates": {
    "PowerSource": {
      "current_output": "300 A"
    }
  },
  "needs_clarification": false,
  "clarification_question": "",
  "confidence_scores": {
    "PowerSource": 1.0
  },
  "reasoning": "User changed their mind from 500A to 300A. Updated current_output to '300 A' (latest value wins)."
}
```

---

### 4.4 Example 4: Ambiguity Detection

**User Message**: "I need aluminum equipment"

**LLM Output**:
```json
{
  "master_json_updates": {},
  "needs_clarification": true,
  "clarification_question": "Are you looking to weld aluminum, or do you need equipment with aluminum components?",
  "confidence_scores": {},
  "reasoning": "Ambiguous: 'aluminum equipment' could mean material to weld (PowerSource.material='aluminum') or wire material (Feeder.material='aluminum'). Need clarification."
}
```

---

### 4.5 Example 5: Multi-Component Extraction

**User Message**: "I need MIG with portable feeder and water cooling"

**LLM Output**:
```json
{
  "master_json_updates": {
    "PowerSource": {
      "process": "MIG (GMAW)"
    },
    "Feeder": {
      "process": "MIG (GMAW)",
      "portability": "portable"
    },
    "Cooler": {
      "cooling_type": "water"
    }
  },
  "needs_clarification": false,
  "clarification_question": "",
  "confidence_scores": {
    "PowerSource": 0.95,
    "Feeder": 0.90,
    "Cooler": 0.95
  },
  "reasoning": "User specified MIG process (applies to PowerSource and Feeder), portable feeder, and water cooling. Normalized all values per spec."
}
```

---

## 5. Prompt Files Structure

```
backend/app/services/extraction/prompts/
├── entity_extraction_system.txt      # System prompt (instructions)
├── entity_extraction_user_template.txt  # User prompt template
├── clarification_examples.txt        # Examples of clarification questions
└── normalization_examples.txt        # Examples of normalization rules
```

---

## 6. Advantages of LLM-Driven Approach

### 6.1 Semantic Understanding

✅ **Natural Language**: Handles variations ("500 amps", "half kilowatt", "500A")
✅ **Context Awareness**: Understands conversation flow and references
✅ **Ambiguity Detection**: Recognizes when clarification needed
✅ **Multi-Component**: Extracts parameters for multiple components in one pass

### 6.2 Automatic Normalization

✅ **Spec Compliance**: LLM normalizes to exact spec format
✅ **Consistent Output**: Temperature=0 ensures deterministic normalization
✅ **Error Recovery**: Handles typos and variations gracefully

### 6.3 Flexibility

✅ **Easy Updates**: Change normalization rules in prompt, not code
✅ **New Components**: Add new component types by updating prompt
✅ **Language Support**: Can extend to multilingual with prompt changes

### 6.4 Transparency

✅ **Reasoning**: LLM explains its extraction decisions
✅ **Confidence Scores**: Provides confidence per component
✅ **Clarification**: Asks questions when uncertain

---

## 7. Testing Strategy

### 7.1 Unit Tests

```python
async def test_simple_extraction():
    """Test basic parameter extraction"""
    extractor = get_llm_entity_extractor(api_key)

    result = await extractor.extract_entities(
        user_message="I need 500 amps",
        current_master_json=MasterParameterJSON(),
        current_state=ConversationState.POWER_SOURCE,
        conversation_history=[]
    )

    assert result.master_json_updates["PowerSource"]["current_output"] == "500 A"
    assert result.needs_clarification == False

async def test_normalization():
    """Test spec-compliant normalization"""
    extractor = get_llm_entity_extractor(api_key)

    test_cases = [
        ("500 amps", "500 A"),
        ("220 volts", "220V"),
        ("3 phase", "3-phase"),
        ("MIG welding", "MIG (GMAW)"),
        (".035 wire", "0.035 inch"),
        ("25 feet", "25 ft")
    ]

    for input_val, expected in test_cases:
        result = await extractor.extract_entities(
            user_message=input_val,
            current_master_json=MasterParameterJSON(),
            current_state=ConversationState.POWER_SOURCE,
            conversation_history=[]
        )

        # Verify normalization
        # (check appropriate component parameter)

async def test_latest_value_wins():
    """Test user changing mind"""
    extractor = get_llm_entity_extractor(api_key)
    master = MasterParameterJSON()

    # First value
    result1 = await extractor.extract_entities(
        user_message="500 amps",
        current_master_json=master,
        current_state=ConversationState.POWER_SOURCE,
        conversation_history=[]
    )
    master = extractor.apply_updates_to_master_json(result1, master)
    assert master.PowerSource.current_output == "500 A"

    # Changed mind
    result2 = await extractor.extract_entities(
        user_message="Actually make it 300 amps",
        current_master_json=master,
        current_state=ConversationState.POWER_SOURCE,
        conversation_history=["500 amps"]
    )
    master = extractor.apply_updates_to_master_json(result2, master)
    assert master.PowerSource.current_output == "300 A"
```

---

## 8. Performance Considerations

### 8.1 LLM Call Optimization

**Caching**:
- System prompt cached by Anthropic (reduces latency)
- User prompt template reused (minimal overhead)

**Batching**:
- Single LLM call per user message
- Extract all components simultaneously

**Token Usage**:
- System prompt: ~2000 tokens (cached)
- User prompt: ~500 tokens (current state + message)
- Output: ~500 tokens (JSON response)
- Total per turn: ~1000 tokens (cached) + ~1000 tokens (uncached) = ~2000 tokens

**Latency**:
- Expected: 1-2 seconds per extraction
- Acceptable for conversational UX

### 8.2 Fallback Strategy

If LLM extraction fails:
1. Log error
2. Return clarification request to user
3. Don't update Master JSON
4. Retry on next turn

---

## 9. Implementation Checklist

- [ ] Create prompts directory structure
- [ ] Write entity_extraction_system.txt prompt
- [ ] Write entity_extraction_user_template.txt prompt
- [ ] Implement LLMEntityExtractor class
- [ ] Add Master Parameter JSON to ConversationHistory
- [ ] Integrate LLM extractor with ConversationalManager
- [ ] Write unit tests for extraction
- [ ] Write unit tests for normalization
- [ ] Test ambiguity detection
- [ ] Test multi-component extraction
- [ ] Load test (token usage, latency)
- [ ] Document API changes

---

## 10. Success Criteria

✅ **Extraction Accuracy**: >95% correct parameter extraction
✅ **Normalization Compliance**: 100% spec-compliant normalization
✅ **Ambiguity Detection**: Correctly identifies ambiguous cases
✅ **Latest Value Wins**: User can change mind, latest always used
✅ **Multi-Component**: Extracts parameters for multiple components
✅ **Performance**: <2 second extraction latency
✅ **Deterministic**: Same input → same output (temperature=0)

---

**Status**: Architecture Complete - Ready for Implementation
**Next**: Create prompt files and implement LLMEntityExtractor
