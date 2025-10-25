"""
Conversation State Models for S1→S7 Flow
Master Parameter JSON + Response JSON + Conversation State
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, create_model
from datetime import datetime
from enum import Enum
import sys
import os

# Add config path for schema loader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.schema_loader import get_component_list


class ConfiguratorState(str, Enum):
    """S1→S7 State Machine States"""
    POWER_SOURCE_SELECTION = "power_source_selection"
    FEEDER_SELECTION = "feeder_selection"
    COOLER_SELECTION = "cooler_selection"
    INTERCONNECTOR_SELECTION = "interconnector_selection"
    TORCH_SELECTION = "torch_selection"
    ACCESSORIES_SELECTION = "accessories_selection"
    FINALIZE = "finalize"


class ComponentApplicability(BaseModel):
    """Component applicability flags for a power source"""
    Feeder: str = "Y"  # Y or N
    Cooler: str = "Y"
    Interconnector: str = "Y"
    Torch: str = "Y"
    Accessories: str = "Y"


def _create_master_parameter_json_model():
    """
    Dynamically create MasterParameterJSON model from schema
    Loads component list from master_parameter_schema.json at runtime
    """
    # Get component list from schema
    component_list = get_component_list()

    # Build field definitions dynamically
    field_definitions = {}

    for component_name in component_list:
        # Each component is a Dict[str, Optional[str]] with empty dict default
        field_definitions[component_name] = (
            Dict[str, Optional[str]],
            Field(default_factory=dict)
        )

    # Add metadata field
    field_definitions['last_updated'] = (datetime, Field(default_factory=datetime.utcnow))

    # Create dynamic model
    DynamicMasterParameterJSON = create_model(
        'MasterParameterJSON',
        __base__=BaseModel,
        __doc__="""
        Master Parameter JSON - Component-Based User Requirements
        Organizes requirements by component for accurate product search
        Each component has its own dict of features
        Components loaded dynamically from master_parameter_schema.json
        """,
        **field_definitions
    )

    # Add example configuration
    DynamicMasterParameterJSON.Config = type('Config', (), {
        'json_schema_extra': {
            "example": {
                "power_source": {
                    "product_name": "Aristo 500ix",
                    "process": "TIG (GTAW)",
                    "current_output": "500 A",
                    "material": "Aluminum"
                },
                "feeder": {
                    "product_name": "RobustFeed",
                    "cooling_type": "Water-cooled"
                },
                "cooler": {
                    "product_name": "Cool2"
                },
                "interconnector": {
                    "cable_length": "5 m"
                },
                "torch": {},
                "accessories": {}
            }
        }
    })

    return DynamicMasterParameterJSON

# Create the model at module load time (cached by schema_loader)
MasterParameterJSON = _create_master_parameter_json_model()


class SelectedProduct(BaseModel):
    """Selected product in Response JSON"""
    gin: str
    name: str
    category: str
    description: Optional[str] = None
    specifications: Dict[str, Any] = Field(default_factory=dict)


class ResponseJSON(BaseModel):
    """
    Response JSON - Selected Products "Cart"
    Tracks user's selected products across S1→S7
    """

    PowerSource: Optional[SelectedProduct] = None
    Feeder: Optional[SelectedProduct] = None
    Cooler: Optional[SelectedProduct] = None
    Interconnector: Optional[SelectedProduct] = None
    Torch: Optional[SelectedProduct] = None
    Accessories: List[SelectedProduct] = Field(default_factory=list)

    # Component Applicability (set after S1 PowerSource selection)
    applicability: Optional[ComponentApplicability] = None

    class Config:
        json_schema_extra = {
            "example": {
                "PowerSource": {
                    "gin": "0446200880",
                    "name": "Aristo 500ix",
                    "category": "PowerSource"
                },
                "Feeder": {
                    "gin": "0123456789",
                    "name": "Wire Feeder XYZ",
                    "category": "Feeder"
                },
                "applicability": {
                    "Feeder": "Y",
                    "Cooler": "Y",
                    "Interconnector": "Y",
                    "Torch": "Y",
                    "Accessories": "Y"
                }
            }
        }


class ConversationState(BaseModel):
    """
    Complete Conversation State
    Combines Master Parameters, Response JSON, and State Machine
    """

    session_id: str
    current_state: ConfiguratorState = ConfiguratorState.POWER_SOURCE_SELECTION

    # Core JSON structures
    master_parameters: MasterParameterJSON = Field(default_factory=MasterParameterJSON)
    response_json: ResponseJSON = Field(default_factory=ResponseJSON)

    # Conversation History
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_updated = datetime.utcnow()

    def update_master_parameters(self, updates: Dict[str, Any]):
        """
        Update master parameters with dict merging
        For component dicts: preserves existing values and adds/updates new ones (latest value wins)
        For metadata fields: replaces with new value
        """
        for key, value in updates.items():
            # Skip metadata field - it's auto-updated
            if key == "last_updated":
                continue

            if hasattr(self.master_parameters, key):
                # Check if this is a component dict (Dict[str, Optional[str]])
                if isinstance(value, dict):
                    # Get existing component dict
                    existing_dict = getattr(self.master_parameters, key, {})

                    # Handle None case
                    if existing_dict is None:
                        existing_dict = {}

                    # Merge: preserve existing + add/update new (latest value wins)
                    merged_dict = {**existing_dict, **value}

                    # Set the merged dict
                    setattr(self.master_parameters, key, merged_dict)

                elif value is not None:
                    # Non-dict field, just set it
                    setattr(self.master_parameters, key, value)

        # Update timestamps
        self.master_parameters.last_updated = datetime.utcnow()
        self.last_updated = datetime.utcnow()

    def select_component(self, component_type: str, product: SelectedProduct):
        """Select a component in Response JSON"""
        if component_type == "Accessories":
            self.response_json.Accessories.append(product)
        else:
            setattr(self.response_json, component_type, product)

        self.last_updated = datetime.utcnow()

    def set_applicability(self, applicability: ComponentApplicability):
        """Set component applicability after PowerSource selection"""
        self.response_json.applicability = applicability

    def get_next_state(self) -> Optional[ConfiguratorState]:
        """
        Determine next state based on applicability and current state
        Automatically skips states where applicability = "N"
        """

        # State progression order
        state_order = [
            ConfiguratorState.POWER_SOURCE_SELECTION,
            ConfiguratorState.FEEDER_SELECTION,
            ConfiguratorState.COOLER_SELECTION,
            ConfiguratorState.INTERCONNECTOR_SELECTION,
            ConfiguratorState.TORCH_SELECTION,
            ConfiguratorState.ACCESSORIES_SELECTION,
            ConfiguratorState.FINALIZE
        ]

        # Get current state index
        try:
            current_idx = state_order.index(self.current_state)
        except ValueError:
            return ConfiguratorState.POWER_SOURCE_SELECTION

        # Find next applicable state
        applicability = self.response_json.applicability

        for next_idx in range(current_idx + 1, len(state_order)):
            next_state = state_order[next_idx]

            # Finalize is always applicable
            if next_state == ConfiguratorState.FINALIZE:
                return next_state

            # Check if component is applicable
            if applicability:
                component_map = {
                    ConfiguratorState.FEEDER_SELECTION: "Feeder",
                    ConfiguratorState.COOLER_SELECTION: "Cooler",
                    ConfiguratorState.INTERCONNECTOR_SELECTION: "Interconnector",
                    ConfiguratorState.TORCH_SELECTION: "Torch",
                    ConfiguratorState.ACCESSORIES_SELECTION: "Accessories"
                }

                component_name = component_map.get(next_state)
                if component_name:
                    # Check applicability
                    is_applicable = getattr(applicability, component_name, "Y") == "Y"
                    if is_applicable:
                        return next_state
                    else:
                        # Auto-skip this state by marking as NA
                        continue
            else:
                # No applicability set yet (before S1 completion)
                return next_state

        # Reached end of states
        return ConfiguratorState.FINALIZE

    def can_finalize(self) -> bool:
        """Check if configuration can be finalized (≥3 real components)"""

        real_components = 0

        if self.response_json.PowerSource:
            real_components += 1
        if self.response_json.Feeder:
            real_components += 1
        if self.response_json.Cooler:
            real_components += 1
        if self.response_json.Interconnector:
            real_components += 1
        if self.response_json.Torch:
            real_components += 1

        real_components += len(self.response_json.Accessories)

        return real_components >= 3

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "current_state": "feeder_selection",
                "master_parameters": {
                    "power_source": {
                        "product_name": "Aristo 500ix",
                        "process": "MIG (GMAW)",
                        "current_output": "500 A"
                    },
                    "feeder": {},
                    "cooler": {},
                    "interconnector": {},
                    "torch": {},
                    "accessories": {}
                },
                "response_json": {
                    "PowerSource": {
                        "gin": "0446200880",
                        "name": "Aristo 500ix",
                        "category": "PowerSource"
                    }
                }
            }
        }
