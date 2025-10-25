# Master Parameter JSON Architecture

**Version**: 1.0
**Date**: 2025-10-24
**Status**: Architecture Design - Critical Component

---

## Executive Summary

The **Master Parameter JSON** is the deterministic semantic bridge between user intent and Neo4j search. It holds normalized, attribute-level parameters per component extracted by the LLM, serving as the single source of truth for what the user wants.

**Spec Reference**: Section 1.1 (Lines 23-94)

---

## 1. Problem Statement

### 1.1 Current State

**Current Implementation**:
- Intent extracted into `EnhancedProcessedIntent` model
- Attributes scattered across multiple models
- No single normalized parameter structure
- Difficult to track what user has specified vs. what's been inferred

**Current Models** (`enhanced_state_models.py`):
```python
class EnhancedProcessedIntent(ExtractedIntent):
    original_query: str
    processed_query: str
    detected_language: LanguageCode
    expertise_mode: ExpertiseMode
    # Attributes are in base ExtractedIntent:
    # - welding_process: List[WeldingProcess]
    # - current_amps: Optional[str]
    # - material: Optional[Material]
    # - thickness_mm: Optional[str]
    # etc.
```

### 1.2 Spec Requirement

**Master Parameter JSON Structure** (Lines 29-62):
```json
{
  "PowerSource": {
    "process": "",
    "current_output": "",
    "duty_cycle": "",
    "material": "",
    "phase": "",
    "voltage": ""
  },
  "Feeder": {
    "process": "",
    "portability": "",
    "wire_size": "",
    "material": ""
  },
  "Cooler": {
    "cooling_type": "",
    "flow_rate": "",
    "capacity": ""
  },
  "Interconnect": {
    "type": "",
    "length": "",
    "connector_type": ""
  },
  "Torch": {
    "process": "",
    "cooling_type": "",
    "material": "",
    "amperage_rating": ""
  }
}
```

### 1.3 Key Requirements from Spec

**1. Attribute Management** (Lines 66-70):
- Attributes refined/overwritten based on latest user input
- Never arbitrarily deleted by system
- User can change their mind - latest value wins

**2. Eligibility for Neo4j Search** (Lines 71-73):
- Component must have ≥1 parameter to be eligible
- Exception: Direct product mentions bypass requirement

**3. Direct Product Mentions** (Lines 75-78):
- Product names trigger direct GIN lookup
- System enriches Master JSON with product attributes from Neo4j

**4. Re-Validation Scope** (Lines 80-83):
- Updating component triggers re-validation ONLY for downstream
- Downstream = all states after modified component

**5. Normalization Standards** (Lines 85-93):
- Current output: "500 A", "300 A"
- Voltage: "230V", "460V"
- Phase: "single-phase", "3-phase"
- Process: "MIG (GMAW)", "TIG (GTAW)", "Stick (SMAW)"
- Cooling type: "water", "air", "none"
- Length: "25 ft", "50 ft"
- Wire size: "0.035 inch", "0.045 inch"

---

## 2. Solution Architecture

### 2.1 Master Parameter JSON Model

**Location**: `/backend/app/models/master_parameter.py`

```python
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

class WeldingProcess(str, Enum):
    """Normalized welding process names"""
    MIG = "MIG (GMAW)"
    TIG = "TIG (GTAW)"
    STICK = "Stick (SMAW)"
    FLUX_CORE = "Flux-Cored (FCAW)"
    SAW = "Submerged Arc (SAW)"


class CoolingType(str, Enum):
    """Normalized cooling types"""
    WATER = "water"
    AIR = "air"
    NONE = "none"


class PhaseType(str, Enum):
    """Normalized phase types"""
    SINGLE = "single-phase"
    THREE = "3-phase"


class PowerSourceParameters(BaseModel):
    """Normalized parameters for Power Source component"""

    process: Optional[str] = ""  # WeldingProcess enum value
    current_output: Optional[str] = ""  # e.g., "500 A"
    duty_cycle: Optional[str] = ""  # e.g., "60%", "100%"
    material: Optional[str] = ""  # e.g., "aluminum", "steel", "stainless"
    phase: Optional[str] = ""  # PhaseType enum value
    voltage: Optional[str] = ""  # e.g., "230V", "460V"

    # Metadata
    has_parameters: bool = False
    direct_product_mention: Optional[str] = None  # e.g., "Aristo 500ix"

    @validator('current_output')
    def normalize_current(cls, v):
        """Normalize current to 'XXX A' format"""
        if not v:
            return v
        # Extract number and add unit
        import re
        match = re.search(r'(\d+)', str(v))
        if match:
            return f"{match.group(1)} A"
        return v

    @validator('voltage')
    def normalize_voltage(cls, v):
        """Normalize voltage to 'XXXV' format"""
        if not v:
            return v
        import re
        match = re.search(r'(\d+)', str(v))
        if match:
            return f"{match.group(1)}V"
        return v

    @validator('phase')
    def normalize_phase(cls, v):
        """Normalize phase to standard format"""
        if not v:
            return v
        v_lower = str(v).lower()
        if '3' in v_lower or 'three' in v_lower:
            return PhaseType.THREE.value
        elif '1' in v_lower or 'single' in v_lower:
            return PhaseType.SINGLE.value
        return v

    def update_from_dict(self, updates: Dict[str, Any]):
        """Update parameters from dict, overwriting existing values"""
        for key, value in updates.items():
            if hasattr(self, key) and value:
                setattr(self, key, value)
        self._update_has_parameters()

    def _update_has_parameters(self):
        """Check if any parameter is set"""
        self.has_parameters = any([
            self.process, self.current_output, self.duty_cycle,
            self.material, self.phase, self.voltage
        ])


class FeederParameters(BaseModel):
    """Normalized parameters for Feeder component"""

    process: Optional[str] = ""
    portability: Optional[str] = ""  # "portable", "stationary"
    wire_size: Optional[str] = ""  # e.g., "0.035 inch", "0.045 inch"
    material: Optional[str] = ""

    # Metadata
    has_parameters: bool = False
    direct_product_mention: Optional[str] = None

    @validator('wire_size')
    def normalize_wire_size(cls, v):
        """Normalize wire size to 'X.XXX inch' format"""
        if not v:
            return v
        import re
        # Extract decimal number
        match = re.search(r'(\d+\.?\d*)', str(v))
        if match:
            size = match.group(1)
            # Ensure leading zero for decimals
            if '.' in size and not size.startswith('0'):
                size = '0' + size
            return f"{size} inch"
        return v

    def update_from_dict(self, updates: Dict[str, Any]):
        """Update parameters from dict"""
        for key, value in updates.items():
            if hasattr(self, key) and value:
                setattr(self, key, value)
        self._update_has_parameters()

    def _update_has_parameters(self):
        self.has_parameters = any([
            self.process, self.portability, self.wire_size, self.material
        ])


class CoolerParameters(BaseModel):
    """Normalized parameters for Cooler component"""

    cooling_type: Optional[str] = ""  # CoolingType enum value
    flow_rate: Optional[str] = ""  # e.g., "2 GPM", "4 GPM"
    capacity: Optional[str] = ""  # e.g., "3 gallon", "5 gallon"

    # Metadata
    has_parameters: bool = False
    direct_product_mention: Optional[str] = None

    @validator('cooling_type')
    def normalize_cooling(cls, v):
        """Normalize cooling type to lowercase"""
        if not v:
            return v
        v_lower = str(v).lower()
        if 'water' in v_lower:
            return CoolingType.WATER.value
        elif 'air' in v_lower:
            return CoolingType.AIR.value
        return v

    def update_from_dict(self, updates: Dict[str, Any]):
        """Update parameters from dict"""
        for key, value in updates.items():
            if hasattr(self, key) and value:
                setattr(self, key, value)
        self._update_has_parameters()

    def _update_has_parameters(self):
        self.has_parameters = any([
            self.cooling_type, self.flow_rate, self.capacity
        ])


class InterconnectorParameters(BaseModel):
    """Normalized parameters for Interconnector component"""

    type: Optional[str] = ""  # Cable type
    length: Optional[str] = ""  # e.g., "25 ft", "50 ft"
    connector_type: Optional[str] = ""

    # Metadata
    has_parameters: bool = False
    direct_product_mention: Optional[str] = None

    @validator('length')
    def normalize_length(cls, v):
        """Normalize length to 'XX ft' format"""
        if not v:
            return v
        import re
        match = re.search(r'(\d+)', str(v))
        if match:
            return f"{match.group(1)} ft"
        return v

    def update_from_dict(self, updates: Dict[str, Any]):
        """Update parameters from dict"""
        for key, value in updates.items():
            if hasattr(self, key) and value:
                setattr(self, key, value)
        self._update_has_parameters()

    def _update_has_parameters(self):
        self.has_parameters = any([
            self.type, self.length, self.connector_type
        ])


class TorchParameters(BaseModel):
    """Normalized parameters for Torch component"""

    process: Optional[str] = ""
    cooling_type: Optional[str] = ""  # CoolingType enum value
    material: Optional[str] = ""
    amperage_rating: Optional[str] = ""  # e.g., "400 A", "500 A"

    # Metadata
    has_parameters: bool = False
    direct_product_mention: Optional[str] = None

    @validator('amperage_rating')
    def normalize_amperage(cls, v):
        """Normalize amperage to 'XXX A' format"""
        if not v:
            return v
        import re
        match = re.search(r'(\d+)', str(v))
        if match:
            return f"{match.group(1)} A"
        return v

    def update_from_dict(self, updates: Dict[str, Any]):
        """Update parameters from dict"""
        for key, value in updates.items():
            if hasattr(self, key) and value:
                setattr(self, key, value)
        self._update_has_parameters()

    def _update_has_parameters(self):
        self.has_parameters = any([
            self.process, self.cooling_type, self.material, self.amperage_rating
        ])


class MasterParameterJSON(BaseModel):
    """
    Master Parameter JSON - Semantic bridge between user intent and Neo4j

    Spec Reference: Section 1.1 (Lines 23-94)

    Holds normalized, attribute-level parameters per component inferred by LLM.
    Acts as single source of truth for user requirements.
    """

    # Component parameters
    PowerSource: PowerSourceParameters = Field(default_factory=PowerSourceParameters)
    Feeder: FeederParameters = Field(default_factory=FeederParameters)
    Cooler: CoolerParameters = Field(default_factory=CoolerParameters)
    Interconnect: InterconnectorParameters = Field(default_factory=InterconnectorParameters)
    Torch: TorchParameters = Field(default_factory=TorchParameters)

    # Metadata
    version: str = "1.0"
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

    # Conversation context
    original_queries: List[str] = Field(default_factory=list)

    def update_component(self, component: str, parameters: Dict[str, Any]):
        """
        Update parameters for a component

        Implements spec requirement: "Attributes refined or overwritten based on latest input"
        Latest value wins - user can change their mind
        """
        if hasattr(self, component):
            component_params = getattr(self, component)
            component_params.update_from_dict(parameters)
            self.last_updated = datetime.now()

    def get_component_parameters(self, component: str) -> Optional[BaseModel]:
        """Get parameters for a component"""
        return getattr(self, component, None)

    def is_component_eligible_for_search(self, component: str) -> bool:
        """
        Check if component has enough parameters for Neo4j search

        Spec requirement: Component must have ≥1 parameter OR direct product mention
        """
        component_params = self.get_component_parameters(component)
        if not component_params:
            return False

        # Direct product mention bypasses parameter requirement
        if component_params.direct_product_mention:
            return True

        # Check if has at least 1 parameter
        return component_params.has_parameters

    def get_search_text(self, component: str) -> str:
        """
        Generate search text for Neo4j embedding search

        Example: "PowerSource 500A 3-phase MIG aluminum"
        """
        component_params = self.get_component_parameters(component)
        if not component_params:
            return ""

        # If direct product mention, use that
        if component_params.direct_product_mention:
            return component_params.direct_product_mention

        # Build search text from parameters
        text_parts = [component]

        for field, value in component_params.dict().items():
            if field in ['has_parameters', 'direct_product_mention']:
                continue
            if value:
                text_parts.append(str(value))

        return " ".join(text_parts)

    def enrich_from_product(self, component: str, product_data: Dict[str, Any]):
        """
        Enrich Master JSON with product attributes from Neo4j node

        Spec requirement: When direct product mentioned, system enriches JSON
        Example: "Aristo 500ix" → add current_output="500 A", process="MIG (GMAW)"
        """
        if component == "PowerSource":
            updates = {}
            if 'current_output' in product_data:
                updates['current_output'] = product_data['current_output']
            if 'process' in product_data:
                updates['process'] = product_data['process']
            if 'voltage' in product_data:
                updates['voltage'] = product_data['voltage']
            if 'phase' in product_data:
                updates['phase'] = product_data['phase']

            self.update_component(component, updates)

        # Similar logic for other components...

    def clear_downstream_components(self, modified_component: str):
        """
        Clear parameters for downstream components

        Spec requirement: Updating component triggers re-validation for downstream only
        Downstream = all states after modified component in S1→S7 sequence
        """
        component_order = [
            "PowerSource",  # S1
            "Feeder",       # S2
            "Cooler",       # S3
            "Interconnect", # S4
            "Torch"         # S5
        ]

        try:
            modified_index = component_order.index(modified_component)
        except ValueError:
            return

        # Clear all downstream components
        for i in range(modified_index + 1, len(component_order)):
            downstream_component = component_order[i]
            # Reset to empty parameters
            if downstream_component == "PowerSource":
                self.PowerSource = PowerSourceParameters()
            elif downstream_component == "Feeder":
                self.Feeder = FeederParameters()
            elif downstream_component == "Cooler":
                self.Cooler = CoolerParameters()
            elif downstream_component == "Interconnect":
                self.Interconnect = InterconnectorParameters()
            elif downstream_component == "Torch":
                self.Torch = TorchParameters()

        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Export as dictionary for API/storage"""
        return {
            "PowerSource": self.PowerSource.dict(),
            "Feeder": self.Feeder.dict(),
            "Cooler": self.Cooler.dict(),
            "Interconnect": self.Interconnect.dict(),
            "Torch": self.Torch.dict(),
            "metadata": {
                "version": self.version,
                "created_at": self.created_at.isoformat(),
                "last_updated": self.last_updated.isoformat(),
                "original_queries": self.original_queries
            }
        }
```

---

## 3. LLM Entity Extraction Service

### 3.1 Intent to Master JSON Converter

**Location**: `/backend/app/services/extraction/master_parameter_extractor.py`

```python
from typing import Dict, Any
from ...models.master_parameter import MasterParameterJSON
from ..enterprise.enhanced_state_models import EnhancedProcessedIntent
import logging

logger = logging.getLogger(__name__)


class MasterParameterExtractor:
    """
    Extracts and normalizes parameters from LLM intent into Master Parameter JSON

    Implements spec Section 7: LLM Semantic Extraction
    """

    def extract_from_intent(
        self,
        intent: EnhancedProcessedIntent,
        master_json: MasterParameterJSON,
        user_message: str
    ) -> MasterParameterJSON:
        """
        Extract parameters from intent and update Master JSON

        Args:
            intent: Processed intent from intelligent_intent_service
            master_json: Current Master Parameter JSON to update
            user_message: Original user message

        Returns:
            Updated Master Parameter JSON
        """

        # Add original query to history
        master_json.original_queries.append(user_message)

        # Extract PowerSource parameters
        ps_params = self._extract_power_source_params(intent)
        if ps_params:
            master_json.update_component("PowerSource", ps_params)

        # Extract Feeder parameters
        feeder_params = self._extract_feeder_params(intent)
        if feeder_params:
            master_json.update_component("Feeder", feeder_params)

        # Extract Cooler parameters
        cooler_params = self._extract_cooler_params(intent)
        if cooler_params:
            master_json.update_component("Cooler", cooler_params)

        # Extract Interconnector parameters
        interconnect_params = self._extract_interconnect_params(intent)
        if interconnect_params:
            master_json.update_component("Interconnect", interconnect_params)

        # Extract Torch parameters
        torch_params = self._extract_torch_params(intent)
        if torch_params:
            master_json.update_component("Torch", torch_params)

        # Check for direct product mentions
        self._detect_product_mentions(user_message, master_json)

        return master_json

    def _extract_power_source_params(self, intent: EnhancedProcessedIntent) -> Dict[str, Any]:
        """Extract PowerSource parameters from intent"""
        params = {}

        # Process
        if hasattr(intent, 'welding_process') and intent.welding_process:
            # welding_process is a list
            processes = [p.value if hasattr(p, 'value') else str(p) for p in intent.welding_process]
            params['process'] = processes[0] if processes else None

        # Current output
        if hasattr(intent, 'current_amps') and intent.current_amps:
            params['current_output'] = str(intent.current_amps)

        # Material
        if hasattr(intent, 'material') and intent.material:
            params['material'] = intent.material.value if hasattr(intent.material, 'value') else str(intent.material)

        # Voltage
        if hasattr(intent, 'voltage') and intent.voltage:
            params['voltage'] = str(intent.voltage)

        # Phase (extract from extracted_entities if available)
        if hasattr(intent, 'extracted_entities') and intent.extracted_entities:
            if 'phase' in intent.extracted_entities:
                params['phase'] = intent.extracted_entities['phase']

        return params

    def _extract_feeder_params(self, intent: EnhancedProcessedIntent) -> Dict[str, Any]:
        """Extract Feeder parameters from intent"""
        params = {}

        # Process (same as power source)
        if hasattr(intent, 'welding_process') and intent.welding_process:
            processes = [p.value if hasattr(p, 'value') else str(p) for p in intent.welding_process]
            params['process'] = processes[0] if processes else None

        # Check extracted_entities for feeder-specific params
        if hasattr(intent, 'extracted_entities') and intent.extracted_entities:
            entities = intent.extracted_entities

            if 'portability' in entities:
                params['portability'] = entities['portability']

            if 'wire_size' in entities:
                params['wire_size'] = entities['wire_size']

        return params

    def _extract_cooler_params(self, intent: EnhancedProcessedIntent) -> Dict[str, Any]:
        """Extract Cooler parameters from intent"""
        params = {}

        if hasattr(intent, 'extracted_entities') and intent.extracted_entities:
            entities = intent.extracted_entities

            if 'cooling_type' in entities:
                params['cooling_type'] = entities['cooling_type']

            if 'flow_rate' in entities:
                params['flow_rate'] = entities['flow_rate']

            if 'capacity' in entities:
                params['capacity'] = entities['capacity']

        return params

    def _extract_interconnect_params(self, intent: EnhancedProcessedIntent) -> Dict[str, Any]:
        """Extract Interconnector parameters from intent"""
        params = {}

        if hasattr(intent, 'extracted_entities') and intent.extracted_entities:
            entities = intent.extracted_entities

            if 'cable_length' in entities:
                params['length'] = entities['cable_length']

            if 'connector_type' in entities:
                params['connector_type'] = entities['connector_type']

        return params

    def _extract_torch_params(self, intent: EnhancedProcessedIntent) -> Dict[str, Any]:
        """Extract Torch parameters from intent"""
        params = {}

        # Process
        if hasattr(intent, 'welding_process') and intent.welding_process:
            processes = [p.value if hasattr(p, 'value') else str(p) for p in intent.welding_process]
            params['process'] = processes[0] if processes else None

        if hasattr(intent, 'extracted_entities') and intent.extracted_entities:
            entities = intent.extracted_entities

            if 'torch_cooling' in entities:
                params['cooling_type'] = entities['torch_cooling']

            if 'torch_amperage' in entities:
                params['amperage_rating'] = entities['torch_amperage']

        return params

    def _detect_product_mentions(self, user_message: str, master_json: MasterParameterJSON):
        """
        Detect direct product name mentions

        Spec: Product names (e.g., "Aristo 500ix") trigger direct GIN lookup
        """
        # Known product patterns
        product_patterns = {
            "Aristo": "PowerSource",
            "Renegade": "PowerSource",
            "Warrior": "PowerSource",
            "Dynasty": "PowerSource",
            "Python": "Feeder",
            "Bernard": "Torch",
            "Tweco": "Torch"
        }

        message_lower = user_message.lower()

        for product_name, component in product_patterns.items():
            if product_name.lower() in message_lower:
                # Extract full product name (e.g., "Aristo 500ix")
                import re
                pattern = f"{product_name}\\s*\\w*"
                match = re.search(pattern, user_message, re.IGNORECASE)
                if match:
                    full_name = match.group(0)

                    # Set direct product mention
                    component_params = master_json.get_component_parameters(component)
                    if component_params:
                        component_params.direct_product_mention = full_name
                        logger.info(f"Detected product mention: {full_name} for {component}")


def get_master_parameter_extractor() -> MasterParameterExtractor:
    """Get extractor instance"""
    return MasterParameterExtractor()
```

---

## 4. Integration with Existing System

### 4.1 Session State Enhancement

**Modify** `/backend/app/models/conversation_models.py`:

```python
from .master_parameter import MasterParameterJSON

class ConversationHistory:
    """Conversation session history"""

    # ... existing fields ...

    # Add Master Parameter JSON
    master_parameters: MasterParameterJSON = Field(default_factory=MasterParameterJSON)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.master_parameters:
            self.master_parameters = MasterParameterJSON()
```

### 4.2 Conversational Manager Integration

**Modify** `/backend/app/services/enterprise/conversational_manager.py`:

```python
from ..extraction.master_parameter_extractor import get_master_parameter_extractor

class ConversationalManager:

    def __init__(self, intent_service, neo4j_service):
        # ... existing initialization ...
        self.parameter_extractor = get_master_parameter_extractor()

    async def _process_turn(self, session, user_message):
        # ... existing logic ...

        # Extract intent
        intent_result = await self.intent_service.process_query(
            query=user_message,
            user_context=user_context,
            trace_id=trace_id
        )

        # UPDATE MASTER PARAMETER JSON
        session.master_parameters = self.parameter_extractor.extract_from_intent(
            intent=intent_result,
            master_json=session.master_parameters,
            user_message=user_message
        )

        # Log extracted parameters
        logger.info(f"Master Parameters updated: {session.master_parameters.to_dict()}")

        # Continue with existing logic...
```

### 4.3 Neo4j Search Integration

**Modify** `/backend/app/services/enterprise/smart_neo4j_service.py`:

```python
async def search_with_master_parameters(
    self,
    component: str,
    master_json: MasterParameterJSON
) -> List[Dict[str, Any]]:
    """
    Search Neo4j using Master Parameter JSON

    Implements spec Section 4.1: Retrieval Strategies
    """

    # Check if component has direct product mention
    component_params = master_json.get_component_parameters(component)
    if not component_params:
        return []

    # Strategy 1: Direct GIN/Model Lookup
    if component_params.direct_product_mention:
        logger.info(f"Using direct product lookup: {component_params.direct_product_mention}")
        return await self._direct_product_lookup(
            component,
            component_params.direct_product_mention
        )

    # Strategy 2: Attribute-Based Embedding Search
    if master_json.is_component_eligible_for_search(component):
        search_text = master_json.get_search_text(component)
        logger.info(f"Using embedding search: {search_text}")
        return await self.search_products_semantic(
            query=search_text,
            category=component
        )

    # Not eligible for search
    logger.warning(f"Component {component} not eligible for search (no parameters)")
    return []
```

---

## 5. User Flow Example

### 5.1 Scenario: User Specifies "Aristo 500ix"

**User Input**: "I need an Aristo 500ix power source"

**Processing**:

1. **Intent Extraction** (intelligent_intent_service):
```python
intent = {
    "original_query": "I need an Aristo 500ix power source",
    "welding_process": [],
    "current_amps": None,
    "extracted_entities": {}
}
```

2. **Master Parameter Extraction**:
```python
# Detect product mention "Aristo 500ix"
master_json.PowerSource.direct_product_mention = "Aristo 500ix"
```

3. **Neo4j Direct Lookup**:
```cypher
MATCH (p:Product)
WHERE p.name CONTAINS "Aristo 500ix"
   OR p.model_name = "Aristo 500ix"
   OR p.gin = "0446200880"
RETURN p
```

4. **Enrich Master JSON from Product**:
```python
product_data = {
    "gin": "0446200880",
    "name": "Aristo 500ix",
    "current_output": "500 A",
    "process": "MIG (GMAW)",
    "voltage": "230V",
    "phase": "3-phase"
}

# Enrich Master JSON
master_json.enrich_from_product("PowerSource", product_data)

# Master JSON now has:
{
  "PowerSource": {
    "process": "MIG (GMAW)",
    "current_output": "500 A",
    "voltage": "230V",
    "phase": "3-phase",
    "direct_product_mention": "Aristo 500ix"
  }
}
```

### 5.2 Scenario: User Changes Mind

**Turn 1**: "I need 500 amps"
```json
{"PowerSource": {"current_output": "500 A"}}
```

**Turn 2**: "Actually, make that 300 amps"
```json
{"PowerSource": {"current_output": "300 A"}}
// Latest value wins!
```

### 5.3 Scenario: Downstream Re-Validation

**Turn 1**: Select Aristo 500ix (500A)
```json
{
  "PowerSource": {"current_output": "500 A"},
  "Feeder": {"process": "MIG (GMAW)"},
  "Cooler": {"cooling_type": "water"},
  "Torch": {"amperage_rating": "500 A"}
}
```

**Turn 2**: User changes to Renegade ES300 (300A)
```python
# Clear downstream components
master_json.update_component("PowerSource", {"current_output": "300 A"})
master_json.clear_downstream_components("PowerSource")

# Result:
{
  "PowerSource": {"current_output": "300 A"},
  "Feeder": {},  // CLEARED
  "Cooler": {},  // CLEARED
  "Torch": {}    // CLEARED
}
```

---

## 6. Benefits

### 6.1 Deterministic Entity Extraction

✅ **Single Source of Truth**: All user requirements in one place
✅ **Normalized Format**: Consistent attribute representation
✅ **Audit Trail**: original_queries tracks conversation history
✅ **Searchable**: Easy to query what user has specified

### 6.2 Flexible Intent Handling

✅ **Latest Value Wins**: User can change mind anytime
✅ **Never Delete**: Attributes only overwritten, never removed arbitrarily
✅ **Downstream Cascade**: Clear dependent components automatically
✅ **Product Enrichment**: Auto-populate from known products

### 6.3 Neo4j Search Optimization

✅ **Eligibility Check**: Only search when ≥1 parameter
✅ **Direct Lookup**: Bypass search for known products
✅ **Semantic Search**: Generate optimal search text from parameters
✅ **Strategy Selection**: Choose best retrieval strategy automatically

---

## 7. Testing

### 7.1 Unit Tests

```python
def test_normalize_current_output():
    """Test current normalization"""
    params = PowerSourceParameters(current_output="500")
    assert params.current_output == "500 A"

    params = PowerSourceParameters(current_output="500 amps")
    assert params.current_output == "500 A"

def test_update_component():
    """Test component update (latest wins)"""
    master = MasterParameterJSON()

    # First update
    master.update_component("PowerSource", {"current_output": "500"})
    assert master.PowerSource.current_output == "500 A"

    # Second update (should overwrite)
    master.update_component("PowerSource", {"current_output": "300"})
    assert master.PowerSource.current_output == "300 A"

def test_clear_downstream():
    """Test downstream clearing"""
    master = MasterParameterJSON()

    # Set all components
    master.update_component("PowerSource", {"current_output": "500 A"})
    master.update_component("Feeder", {"process": "MIG (GMAW)"})
    master.update_component("Torch", {"amperage_rating": "500 A"})

    # Modify PowerSource (should clear Feeder and Torch)
    master.clear_downstream_components("PowerSource")

    assert master.PowerSource.current_output == "500 A"  # Unchanged
    assert master.Feeder.process == ""  # Cleared
    assert master.Torch.amperage_rating == ""  # Cleared
```

---

## 8. API Response Format

### 8.1 Include Master JSON in Response

```python
class ConversationQueryResponse(BaseModel):
    # ... existing fields ...

    master_parameters: Optional[Dict[str, Any]] = None

    @classmethod
    def from_session(cls, session: ConversationHistory):
        return cls(
            # ... existing fields ...
            master_parameters=session.master_parameters.to_dict()
        )
```

**Example Response**:
```json
{
  "session_id": "abc-123",
  "message": "I've found the Aristo 500ix...",
  "current_state": "FEEDER",
  "master_parameters": {
    "PowerSource": {
      "process": "MIG (GMAW)",
      "current_output": "500 A",
      "voltage": "230V",
      "phase": "3-phase",
      "direct_product_mention": "Aristo 500ix",
      "has_parameters": true
    },
    "Feeder": {},
    "Cooler": {},
    "Interconnect": {},
    "Torch": {},
    "metadata": {
      "version": "1.0",
      "created_at": "2025-10-24T10:00:00",
      "last_updated": "2025-10-24T10:01:30",
      "original_queries": [
        "I need an Aristo 500ix power source"
      ]
    }
  }
}
```

---

## 9. Implementation Checklist

- [ ] Create `master_parameter.py` with all component parameter models
- [ ] Add normalization validators for each attribute type
- [ ] Implement `MasterParameterExtractor` service
- [ ] Integrate with `ConversationHistory` model
- [ ] Update `ConversationalManager` to use Master JSON
- [ ] Enhance `SmartNeo4jService` with parameter-based search
- [ ] Add Master JSON to API responses
- [ ] Write unit tests for normalization
- [ ] Write unit tests for update logic
- [ ] Write integration tests for user flow scenarios
- [ ] Document API changes in Swagger/OpenAPI

---

## 10. Success Criteria

✅ **Deterministic Extraction**: Same input always produces same Master JSON
✅ **Normalization Accuracy**: 100% of test cases normalize correctly
✅ **Latest Value Wins**: User can change mind, latest value always used
✅ **Downstream Cascade**: Modifying component clears all downstream
✅ **Product Enrichment**: Direct mentions auto-populate attributes
✅ **Search Eligibility**: Correct strategy selection (direct vs semantic)

---

**Status**: Architecture Design Complete - Ready for Implementation
**Next**: Integrate with Phase 1 implementation plan
