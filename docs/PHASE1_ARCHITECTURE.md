# Phase 1 Architecture: Spec Alignment Implementation

**Version**: 1.0
**Date**: 2025-10-24
**Status**: Architecture Design - Awaiting Approval

---

## Executive Summary

This document defines the architecture for aligning our current system with the v5.4 specification requirements, focusing on **4 critical gaps** that need immediate implementation:

1. **Power Source Component Configuration** (Priority 1)
2. **Component Threshold Validation** (Priority 2)
3. **Dynamic State Skipping** (Priority 3)
4. **NA Auto-Fill Mechanism** (Priority 4)

---

## 1. Power Source Component Configuration System

### 1.1 Problem Statement

**Current State**: No static configuration defining which components are applicable for each power source. Component applicability is either hardcoded or inferred from Neo4j relationships.

**Spec Requirement** (Lines 153-214): Static JSON configuration file that defines Y/N applicability per component per power source, driving state machine behavior.

**Impact**: Configuration changes require code/graph updates instead of simple JSON edits. No single source of truth for component applicability.

---

### 1.2 Solution Architecture

#### Component Applicability Configuration File

**Location**: `/backend/app/config/component_applicability.json`

**Structure**:
```json
{
  "version": "1.0",
  "last_updated": "2025-10-24T00:00:00Z",
  "default_policy": {
    "Feeder": "Y",
    "Cooler": "Y",
    "Interconnector": "Y",
    "Torch": "Y",
    "Accessories": "Y"
  },
  "power_sources": {
    "0446200880": {
      "name": "Aristo 500ix",
      "applicability": {
        "Feeder": "Y",
        "Cooler": "Y",
        "Interconnector": "Y",
        "Torch": "Y",
        "Accessories": "Y"
      }
    },
    "0445250880": {
      "name": "Renegade ES 300i",
      "applicability": {
        "Feeder": "N",
        "Cooler": "N",
        "Interconnector": "N",
        "Torch": "Y",
        "Accessories": "Y"
      }
    },
    "0465350884": {
      "name": "Warrior 400i",
      "applicability": {
        "Feeder": "Y",
        "Cooler": "Y",
        "Interconnector": "Y",
        "Torch": "Y",
        "Accessories": "Y"
      }
    },
    "0465350883": {
      "name": "Warrior 500i",
      "applicability": {
        "Feeder": "Y",
        "Cooler": "Y",
        "Interconnector": "Y",
        "Torch": "Y",
        "Accessories": "Y"
      }
    },
    "0445555880": {
      "name": "Warrior 750i",
      "applicability": {
        "Feeder": "Y",
        "Cooler": "Y",
        "Interconnector": "Y",
        "Torch": "Y",
        "Accessories": "Y"
      }
    }
  },
  "validation_rules": {
    "Y": "Component is required and must be selected or explicitly skipped",
    "N": "Component is not applicable and will be auto-filled as NA"
  }
}
```

#### Configuration Manager Service

**Location**: `/backend/app/services/configuration/component_config_manager.py`

**Class Design**:
```python
from typing import Dict, Optional
from pathlib import Path
import json
from datetime import datetime

class ComponentApplicability:
    """Component applicability for a power source"""

    def __init__(self, config_dict: Dict[str, str]):
        self.feeder: str = config_dict.get("Feeder", "Y")
        self.cooler: str = config_dict.get("Cooler", "Y")
        self.interconnector: str = config_dict.get("Interconnector", "Y")
        self.torch: str = config_dict.get("Torch", "Y")
        self.accessories: str = config_dict.get("Accessories", "Y")

    def is_required(self, component: str) -> bool:
        """Check if component is required (Y)"""
        return getattr(self, component.lower(), "Y") == "Y"

    def is_not_applicable(self, component: str) -> bool:
        """Check if component is not applicable (N)"""
        return getattr(self, component.lower(), "Y") == "N"

    def get_active_components(self) -> List[str]:
        """Get list of components marked as Y"""
        return [
            comp for comp in ["Feeder", "Cooler", "Interconnector", "Torch", "Accessories"]
            if getattr(self, comp.lower()) == "Y"
        ]

    def get_na_components(self) -> List[str]:
        """Get list of components marked as N (to be auto-filled as NA)"""
        return [
            comp for comp in ["Feeder", "Cooler", "Interconnector", "Torch", "Accessories"]
            if getattr(self, comp.lower()) == "N"
        ]


class ComponentConfigManager:
    """Manages component applicability configuration"""

    _instance = None
    _config_cache: Optional[Dict] = None
    _cache_timestamp: Optional[datetime] = None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.config_path = Path(__file__).parent.parent.parent / "config" / "component_applicability.json"
        self.default_applicability = ComponentApplicability({
            "Feeder": "Y",
            "Cooler": "Y",
            "Interconnector": "Y",
            "Torch": "Y",
            "Accessories": "Y"
        })

    def _load_config(self) -> Dict:
        """Load configuration from file with caching"""

        # Check cache freshness (reload every 5 minutes)
        if self._config_cache and self._cache_timestamp:
            age = (datetime.now() - self._cache_timestamp).total_seconds()
            if age < 300:  # 5 minutes
                return self._config_cache

        # Load from file
        if not self.config_path.exists():
            logger.warning(f"Component config not found at {self.config_path}, using defaults")
            return {"power_sources": {}, "default_policy": {}}

        with open(self.config_path, 'r') as f:
            config = json.load(f)

        # Update cache
        self._config_cache = config
        self._cache_timestamp = datetime.now()

        return config

    def get_applicability(self, power_source_gin: str) -> ComponentApplicability:
        """
        Get component applicability for a power source

        Args:
            power_source_gin: GIN of the power source

        Returns:
            ComponentApplicability object with Y/N flags
        """
        config = self._load_config()

        # Check if power source exists in config
        if power_source_gin in config.get("power_sources", {}):
            ps_config = config["power_sources"][power_source_gin]
            return ComponentApplicability(ps_config["applicability"])

        # Fallback to default policy
        logger.warning(f"Power source {power_source_gin} not found in config, using default policy")
        default_policy = config.get("default_policy", {})
        return ComponentApplicability(default_policy) if default_policy else self.default_applicability

    def reload_config(self):
        """Force reload configuration from file"""
        self._config_cache = None
        self._cache_timestamp = None
        return self._load_config()

    def get_all_power_sources(self) -> Dict[str, str]:
        """Get all configured power sources"""
        config = self._load_config()
        return {
            gin: ps_config["name"]
            for gin, ps_config in config.get("power_sources", {}).items()
        }


# Singleton instance
_config_manager = None

def get_component_config_manager() -> ComponentConfigManager:
    """Get singleton instance of config manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ComponentConfigManager()
    return _config_manager
```

---

### 1.3 Integration Points

**1. State Machine Integration** (`configuration_state_machine.py`):
```python
from ..configuration.component_config_manager import get_component_config_manager

class ConfigurationStateMachine:

    def __init__(self):
        self.config_manager = get_component_config_manager()
        # ... existing initialization

    def get_active_states_for_power_source(self, power_source_gin: str) -> List[ConversationState]:
        """
        Get list of active states based on power source configuration

        Returns states that should be processed (Y components)
        """
        applicability = self.config_manager.get_applicability(power_source_gin)

        states = [ConversationState.POWER_SOURCE]  # Always start here

        if applicability.is_required("Feeder"):
            states.append(ConversationState.FEEDER)

        if applicability.is_required("Cooler"):
            states.append(ConversationState.COOLER)

        if applicability.is_required("Interconnector"):
            states.append(ConversationState.INTERCONNECTOR)

        if applicability.is_required("Torch"):
            states.append(ConversationState.TORCH)

        if applicability.is_required("Accessories"):
            states.append(ConversationState.ACCESSORIES)

        states.extend([
            ConversationState.PACKAGE_COMPLETION,
            ConversationState.REVIEW,
            ConversationState.CONFIRMATION
        ])

        return states
```

**2. Conversational Manager Integration** (`conversational_manager.py`):
```python
async def _handle_power_source_selection(self, session, user_message):
    # ... existing power source selection logic ...

    # After power source is selected:
    power_source_gin = session.partial_package.power_source.gin

    # Get component applicability
    applicability = self.state_machine.config_manager.get_applicability(power_source_gin)

    # Store in session for quick access
    session.component_applicability = applicability

    # Auto-fill NA components immediately (see NA Auto-Fill section)
    await self._auto_fill_na_components(session, applicability)

    # Determine next state based on configuration
    next_state = self._get_next_active_state(session, ConversationState.POWER_SOURCE)

    return message, [], next_state
```

---

## 2. Component Threshold Validation

### 2.1 Problem Statement

**Current State**: No validation enforcing ≥3 real components before package generation.

**Spec Requirement** (Lines 289-322): Backend trigger requires counting real components (gin != "" AND gin != "NA") and ensuring count ≥ 3 before proceeding.

**Impact**: May generate packages with insufficient configuration data.

---

### 2.2 Solution Architecture

#### Component Counter Utility

**Location**: `/backend/app/services/validators/component_validator.py`

**Class Design**:
```python
from typing import Tuple, List
from ...models.conversation_models import PartialPackage, ComponentSelection

class ComponentValidator:
    """Validates component selections and counts"""

    MIN_REAL_COMPONENTS = 3

    @staticmethod
    def is_real_component(component: Optional[ComponentSelection]) -> bool:
        """
        Check if component is a real selection

        Real component: gin != "" AND gin != "NA"
        """
        if component is None:
            return False

        if not component.gin or component.gin == "":
            return False

        if component.gin.upper() == "NA":
            return False

        return True

    @staticmethod
    def count_real_components(partial_package: PartialPackage) -> int:
        """
        Count real components in package

        Returns: Number of real components (excludes empty and NA)
        """
        count = 0

        if ComponentValidator.is_real_component(partial_package.power_source):
            count += 1

        if ComponentValidator.is_real_component(partial_package.feeder):
            count += 1

        if ComponentValidator.is_real_component(partial_package.cooler):
            count += 1

        if ComponentValidator.is_real_component(partial_package.interconnector):
            count += 1

        if ComponentValidator.is_real_component(partial_package.torch):
            count += 1

        # Count accessories
        for accessory in partial_package.accessories:
            if ComponentValidator.is_real_component(accessory):
                count += 1

        return count

    @staticmethod
    def validate_threshold(partial_package: PartialPackage) -> Tuple[bool, str, List[str]]:
        """
        Validate component threshold requirement

        Returns:
            (is_valid, message, missing_components)
        """
        real_count = ComponentValidator.count_real_components(partial_package)

        if real_count >= ComponentValidator.MIN_REAL_COMPONENTS:
            return True, f"Package has {real_count} components (≥3 required)", []

        # Identify missing components
        missing = []

        if not ComponentValidator.is_real_component(partial_package.power_source):
            missing.append("PowerSource")

        if not ComponentValidator.is_real_component(partial_package.feeder):
            missing.append("Feeder")

        if not ComponentValidator.is_real_component(partial_package.cooler):
            missing.append("Cooler")

        if not ComponentValidator.is_real_component(partial_package.interconnector):
            missing.append("Interconnector")

        if not ComponentValidator.is_real_component(partial_package.torch):
            missing.append("Torch")

        shortage = ComponentValidator.MIN_REAL_COMPONENTS - real_count
        message = f"Package needs at least 3 components to generate packages. Currently have {real_count}. Need {shortage} more."

        return False, message, missing


def get_component_validator() -> ComponentValidator:
    """Get component validator instance"""
    return ComponentValidator()
```

---

### 2.3 Integration Points

**1. Package Completion Handler** (`conversational_manager.py`):
```python
async def _handle_package_completion(self, session, user_message):
    # ... existing logic ...

    # VALIDATE THRESHOLD BEFORE CALLING ORCHESTRATOR
    validator = get_component_validator()
    is_valid, message, missing = validator.validate_threshold(session.partial_package)

    if not is_valid:
        # Threshold not met - inform user and stay in current state
        response = f"{message}\n\n"
        response += "Current configuration:\n"

        real_count = validator.count_real_components(session.partial_package)
        for component in ["power_source", "feeder", "cooler", "interconnector", "torch"]:
            comp_obj = getattr(session.partial_package, component, None)
            if validator.is_real_component(comp_obj):
                response += f"✅ {component.title()}: {comp_obj.name}\n"
            elif comp_obj and comp_obj.gin == "NA":
                response += f"⚪ {component.title()}: Not Applicable\n"
            else:
                response += f"❌ {component.title()}: Not selected\n"

        response += f"\nWould you like to add more components?"

        return response, ["Yes", "Cancel"], ConversationState.PACKAGE_COMPLETION

    # Threshold met - proceed with orchestrator
    # ... existing orchestrator call ...
```

**2. Termination Intent Handler**:
```python
async def handle_termination_intent(self, session, user_message):
    """
    Handle user termination keywords: "done", "finish", "complete", etc.
    Implements spec Section 6: Termination Intent Handling
    """

    # Get current state and component count
    current_state = session.current_state
    validator = get_component_validator()
    real_count = validator.count_real_components(session.partial_package)

    # Case 1: S1-S6 with < 3 components (Lines 554)
    if current_state != ConversationState.PACKAGE_COMPLETION and real_count < 3:
        is_valid, message, missing = validator.validate_threshold(session.partial_package)
        response = f"{message}\n\nWould you like to continue configuring?"
        return response, ["Yes", "Cancel"], current_state  # DO NOT reset

    # Case 2: S1-S6 with ≥ 3 components (Lines 555)
    if current_state != ConversationState.PACKAGE_COMPLETION and real_count >= 3:
        # Fast-forward to S7 (Package Completion)
        # Lock all current selections
        response = "Great! You have enough components. Let me summarize your configuration:\n\n"
        # ... generate summary ...
        response += "\n\nReady to generate packages with this configuration?"
        return response, ["Yes", "Make changes"], ConversationState.PACKAGE_COMPLETION

    # Case 3: S7 with ≥ 3 components (Lines 556)
    if current_state == ConversationState.PACKAGE_COMPLETION and real_count >= 3:
        # Check for user confirmation and trigger backend
        # ... existing logic ...
        pass
```

---

## 3. Dynamic State Skipping

### 3.1 Problem Statement

**Current State**: State machine always progresses through all states sequentially, regardless of power source configuration.

**Spec Requirement** (Lines 252-286): Dynamic state path based on power source config. Components marked "N" should be auto-skipped, system should jump directly to next "Y" component.

**Impact**: Inefficient UX for minimal configurations (e.g., Renegade ES300 doesn't need Feeder/Cooler).

---

### 3.2 Solution Architecture

#### Dynamic State Navigator

**Enhancement to** `/backend/app/services/enterprise/configuration_state_machine.py`:

```python
from typing import Optional
from ...models.conversation_models import ConversationState, PartialPackage

class ConfigurationStateMachine:

    def get_next_state(
        self,
        current_state: ConversationState,
        partial_package: PartialPackage
    ) -> ConversationState:
        """
        Get next state based on current state and power source configuration

        Uses component applicability to skip N components dynamically
        """

        # If no power source selected, follow standard progression
        if not partial_package.power_source or not partial_package.power_source.gin:
            return self._get_standard_next_state(current_state)

        # Get applicability configuration
        power_source_gin = partial_package.power_source.gin
        applicability = self.config_manager.get_applicability(power_source_gin)

        # Get active states for this power source
        active_states = self._get_active_states(applicability)

        # Find current state index
        try:
            current_index = active_states.index(current_state)
        except ValueError:
            # Current state not in active states (shouldn't happen)
            logger.warning(f"Current state {current_state} not in active states")
            return self._get_standard_next_state(current_state)

        # Return next active state
        if current_index + 1 < len(active_states):
            return active_states[current_index + 1]
        else:
            return ConversationState.COMPLETE

    def _get_active_states(self, applicability: ComponentApplicability) -> List[ConversationState]:
        """Build list of active states based on applicability"""

        states = [ConversationState.POWER_SOURCE]

        if applicability.is_required("Feeder"):
            states.append(ConversationState.FEEDER)

        if applicability.is_required("Cooler"):
            states.append(ConversationState.COOLER)

        if applicability.is_required("Interconnector"):
            states.append(ConversationState.INTERCONNECTOR)

        if applicability.is_required("Torch"):
            states.append(ConversationState.TORCH)

        if applicability.is_required("Accessories"):
            states.append(ConversationState.ACCESSORIES)

        # Always include these final states
        states.extend([
            ConversationState.PACKAGE_COMPLETION,
            ConversationState.REVIEW,
            ConversationState.CONFIRMATION
        ])

        return states

    def _get_standard_next_state(self, current_state: ConversationState) -> ConversationState:
        """Fallback standard progression (all states)"""
        state_order = [
            ConversationState.GREETING,
            ConversationState.POWER_SOURCE,
            ConversationState.FEEDER,
            ConversationState.COOLER,
            ConversationState.INTERCONNECTOR,
            ConversationState.TORCH,
            ConversationState.ACCESSORIES,
            ConversationState.PACKAGE_COMPLETION,
            ConversationState.REVIEW,
            ConversationState.CONFIRMATION,
            ConversationState.COMPLETE
        ]

        try:
            current_index = state_order.index(current_state)
            if current_index + 1 < len(state_order):
                return state_order[current_index + 1]
        except ValueError:
            pass

        return ConversationState.COMPLETE
```

---

### 3.3 Integration Example

**Scenario: Renegade ES300 Configuration**

```python
# Power source config for Renegade ES300:
{
  "Feeder": "N",
  "Cooler": "N",
  "Interconnector": "N",
  "Torch": "Y",
  "Accessories": "Y"
}

# Active states generated:
[
  POWER_SOURCE,      # S1
  TORCH,             # S5 (skipped S2, S3, S4)
  ACCESSORIES,       # S6
  PACKAGE_COMPLETION,# S7
  REVIEW,
  CONFIRMATION
]

# State progression:
POWER_SOURCE → TORCH → ACCESSORIES → PACKAGE_COMPLETION
```

---

## 4. NA Auto-Fill Mechanism

### 4.1 Problem Statement

**Current State**: No automatic NA filling when power source is selected. "N" components handled manually.

**Spec Requirement** (Lines 137-145, 263): Components marked "N" should be auto-filled as `{"gin": "NA", "description": "Not Applicable"}` immediately after power source selection, in a single operation.

**Impact**: Manual handling required, inconsistent NA representation.

---

### 4.2 Solution Architecture

#### NA Auto-Fill Service

**Location**: `/backend/app/services/configuration/na_autofill_service.py`

```python
from typing import List
from ...models.conversation_models import PartialPackage, ComponentSelection
from .component_config_manager import ComponentApplicability
import logging

logger = logging.getLogger(__name__)

class NAComponent:
    """Factory for NA component selections"""

    @staticmethod
    def create(category: str) -> ComponentSelection:
        """Create NA component for given category"""
        return ComponentSelection(
            gin="NA",
            name=f"Not Applicable - {category}",
            category=category,
            description="Not Applicable",
            confidence=1.0
        )


class NAAutoFillService:
    """Auto-fills NA components based on power source configuration"""

    def auto_fill_na_components(
        self,
        partial_package: PartialPackage,
        applicability: ComponentApplicability
    ) -> List[str]:
        """
        Auto-fill all N components as NA immediately

        Args:
            partial_package: Current package to update
            applicability: Component applicability config

        Returns:
            List of component names that were auto-filled
        """
        filled_components = []

        # Feeder
        if applicability.is_not_applicable("Feeder"):
            partial_package.feeder = NAComponent.create("Feeder")
            filled_components.append("Feeder")
            logger.info("Auto-filled Feeder as NA")

        # Cooler
        if applicability.is_not_applicable("Cooler"):
            partial_package.cooler = NAComponent.create("Cooler")
            filled_components.append("Cooler")
            logger.info("Auto-filled Cooler as NA")

        # Interconnector
        if applicability.is_not_applicable("Interconnector"):
            partial_package.interconnector = NAComponent.create("Interconnector")
            filled_components.append("Interconnector")
            logger.info("Auto-filled Interconnector as NA")

        # Torch
        if applicability.is_not_applicable("Torch"):
            partial_package.torch = NAComponent.create("Torch")
            filled_components.append("Torch")
            logger.info("Auto-filled Torch as NA")

        # Accessories
        if applicability.is_not_applicable("Accessories"):
            # For accessories, we just mark that they're skipped
            # Don't create ComponentSelection since accessories is a list
            filled_components.append("Accessories")
            logger.info("Marked Accessories as NA (skipped)")

        return filled_components

    def get_na_summary(self, filled_components: List[str]) -> str:
        """Generate user-friendly summary of NA auto-fill"""
        if not filled_components:
            return ""

        summary = "The following components are not applicable for your power source and have been automatically set:\n"
        for component in filled_components:
            summary += f"• {component}: Not Applicable\n"

        return summary


def get_na_autofill_service() -> NAAutoFillService:
    """Get NA auto-fill service instance"""
    return NAAutoFillService()
```

---

### 4.3 Integration Points

**1. Power Source Selection Handler** (`conversational_manager.py`):

```python
from ..configuration.na_autofill_service import get_na_autofill_service
from ..configuration.component_config_manager import get_component_config_manager

async def _handle_power_source_selection(self, session, user_message):
    # ... existing power source selection logic ...

    # After power source is confirmed:
    power_source_gin = session.partial_package.power_source.gin

    # Get component applicability
    config_manager = get_component_config_manager()
    applicability = config_manager.get_applicability(power_source_gin)

    # AUTO-FILL NA COMPONENTS IMMEDIATELY (SPEC REQUIREMENT)
    na_service = get_na_autofill_service()
    filled_components = na_service.auto_fill_na_components(
        session.partial_package,
        applicability
    )

    # Generate confirmation message
    message = self.response_generator.generate_power_source_confirmation(
        expertise_mode=session.expertise_mode,
        power_source=session.partial_package.power_source,
        requirements=session.partial_package.requirements
    )

    # Add NA auto-fill summary if any components were filled
    if filled_components:
        na_summary = na_service.get_na_summary(filled_components)
        message += f"\n\n{na_summary}"

    # Get next active state (will skip N components automatically)
    next_state = self.state_machine.get_next_state(
        ConversationState.POWER_SOURCE,
        session.partial_package
    )

    return message, [], next_state
```

**2. Response JSON Representation**:

```python
# When serializing Response JSON for backend
def serialize_response_json(partial_package: PartialPackage) -> dict:
    """Serialize partial package to Response JSON format"""

    response = {}

    # Power Source
    if partial_package.power_source:
        response["PowerSource"] = {
            "gin": partial_package.power_source.gin,
            "description": partial_package.power_source.name
        }

    # Feeder (may be NA)
    if partial_package.feeder:
        response["Feeder"] = {
            "gin": partial_package.feeder.gin,  # May be "NA"
            "description": partial_package.feeder.description
        }

    # ... similarly for other components ...

    return response
```

---

## 5. Integration Summary

### 5.1 Modified Files

| File | Type | Changes |
|------|------|---------|
| `/backend/app/config/component_applicability.json` | **NEW** | Component Y/N configuration |
| `/backend/app/services/configuration/component_config_manager.py` | **NEW** | Configuration manager service |
| `/backend/app/services/validators/component_validator.py` | **NEW** | Threshold validation |
| `/backend/app/services/configuration/na_autofill_service.py` | **NEW** | NA auto-fill service |
| `/backend/app/services/enterprise/configuration_state_machine.py` | **MODIFY** | Add dynamic state skipping |
| `/backend/app/services/enterprise/conversational_manager.py` | **MODIFY** | Integrate all 4 systems |
| `/backend/app/models/conversation_models.py` | **MODIFY** | Add ComponentSelection support for NA |

---

### 5.2 Data Flow

```
User selects Power Source
    ↓
[1] ComponentConfigManager.get_applicability(gin)
    ↓
[2] NAAutoFillService.auto_fill_na_components(package, applicability)
    → Sets Feeder/Cooler/etc to NA if configured as "N"
    ↓
[3] StateMachine.get_next_state(current_state, package)
    → Uses applicability to skip N states
    → Returns next Y state
    ↓
[4] Continue conversation at next active state
    ↓
... (repeat for each component) ...
    ↓
User triggers completion
    ↓
[5] ComponentValidator.validate_threshold(package)
    → Count real components (≥3 required)
    → If valid: proceed to orchestrator
    → If invalid: inform user and stay in state
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

**Test Coverage Required**:

1. **ComponentConfigManager**:
   - Load configuration from file
   - Cache mechanism
   - Fallback to defaults
   - Get applicability for known/unknown power sources

2. **ComponentValidator**:
   - Count real components correctly
   - Exclude NA components from count
   - Validate threshold with various package states
   - Generate correct missing component lists

3. **NAAutoFillService**:
   - Auto-fill correct components based on config
   - Generate accurate summaries
   - Handle edge cases (all Y, all N, mixed)

4. **Dynamic State Skipping**:
   - Generate correct active state list
   - Skip N states properly
   - Handle standard progression fallback

---

### 6.2 Integration Tests

**Test Scenarios** (from Spec Section 11.1):

1. **Happy Path (Aristo 500ix - All Y)**:
   - Expected flow: PS → Feeder → Cooler → Interconnector → Torch → Accessories → Complete
   - No NA auto-fill
   - All states active

2. **Minimal Config (Renegade ES300 - Minimal Y)**:
   - Expected flow: PS → Torch → Accessories → Complete
   - Auto-fill: Feeder, Cooler, Interconnector as NA
   - States skipped: Feeder, Cooler, Interconnector

3. **Threshold Validation**:
   - User with only PowerSource tries to finish → Blocked
   - User with 3+ components tries to finish → Allowed

4. **NA Counting**:
   - Package with 2 real + 3 NA → Count = 2 (blocked)
   - Package with 3 real + 2 NA → Count = 3 (allowed)

---

## 7. Deployment Plan

### 7.1 Implementation Sequence

**Week 1**:
1. Create `component_applicability.json` with all known power sources
2. Implement `ComponentConfigManager`
3. Unit tests for config manager

**Week 2**:
4. Implement `ComponentValidator`
5. Integrate threshold validation into package completion
6. Unit tests for validator

**Week 3**:
7. Implement `NAAutoFillService`
8. Integrate NA auto-fill into power source selection
9. Unit tests for NA service

**Week 4**:
10. Enhance state machine with dynamic skipping
11. Integrate all 4 systems into conversational manager
12. Integration tests for all scenarios

---

### 7.2 Rollback Plan

**If issues arise**:

1. **Config Manager**: Falls back to default "all Y" behavior
2. **Threshold Validation**: Can be disabled via feature flag
3. **NA Auto-Fill**: Falls back to manual handling
4. **Dynamic Skipping**: Falls back to standard progression

All components designed with graceful degradation.

---

## 8. Success Criteria

✅ **Power Source Configuration**:
- [ ] JSON configuration file exists with all power sources
- [ ] Config manager loads and caches configuration correctly
- [ ] Changes to JSON immediately affect behavior (within cache TTL)

✅ **Component Threshold Validation**:
- [ ] System blocks package generation with < 3 real components
- [ ] NA components correctly excluded from count
- [ ] Clear user feedback when threshold not met

✅ **Dynamic State Skipping**:
- [ ] System skips N states automatically
- [ ] Aristo 500ix goes through all states
- [ ] Renegade ES300 skips Feeder/Cooler/Interconnector

✅ **NA Auto-Fill**:
- [ ] N components auto-filled immediately after power source selection
- [ ] User notified of auto-fill actions
- [ ] NA components properly represented in Response JSON

✅ **Integration**:
- [ ] All 6 spec test scenarios pass
- [ ] No regression in existing functionality
- [ ] Performance impact < 50ms per state transition

---

## 9. Open Questions for Approval

1. **Cache TTL**: Is 5 minutes acceptable for config cache, or should it be configurable?

2. **NA Representation**: Should NA components have their own category or use the original category?

3. **Threshold Override**: Should there be an admin override to allow < 3 components for testing?

4. **State Skipping Notification**: Should we explicitly tell users "Skipping Feeder because not applicable" or just move to next state silently?

5. **Configuration Versioning**: Should we implement version migration for config file updates?

---

## 10. Next Steps

**Awaiting Approval** for:
1. Architecture approach (config-driven vs code-driven)
2. Component counting rules (confirm NA exclusion is correct)
3. State skipping UX (explicit vs implicit)
4. Implementation timeline (4 weeks acceptable?)

**Upon Approval**:
1. Create GitHub issues for each component
2. Begin Week 1 implementation (Config Manager)
3. Daily standups to track progress
4. Code review checkpoints at end of each week

---

**Document Status**: Ready for Review
**Next Review Date**: TBD
**Approval Required From**: Product Owner, Tech Lead

