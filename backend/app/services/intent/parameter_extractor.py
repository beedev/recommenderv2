"""
Simplified Parameter Extraction Service for S1→S7 Flow
Extracts user requirements using LLM-based parameter extraction
Component-based structure with product name knowledge
Schema-driven component list from master_parameter_schema.json
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
import sys

# Add config path for schema loader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from config.schema_loader import get_component_list

logger = logging.getLogger(__name__)


class ParameterExtractor:
    """
    LLM-based parameter extraction for welding requirements
    Component-based extraction with product name recognition
    """

    def __init__(self, openai_api_key: str):
        """Initialize parameter extractor with OpenAI client"""
        self.client = AsyncOpenAI(api_key=openai_api_key)

        # Load product names for PowerSource, Feeder, Cooler only
        self.product_names = self._load_product_names()

        logger.info("Parameter Extractor initialized with product name knowledge")

    def _load_product_names(self) -> Dict[str, List[str]]:
        """Load product names from config file (limited to PowerSource, Feeder, Cooler)"""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "../../config/product_names.json"
            )

            with open(config_path, "r") as f:
                all_products = json.load(f)

            # Only include PowerSource, Feeder, Cooler to avoid huge prompts
            limited_products = {
                "power_source": all_products.get("power_source", []),
                "feeder": all_products.get("feeder", []),
                "cooler": all_products.get("cooler", [])
            }

            logger.info(f"Loaded product names: {sum(len(v) for v in limited_products.values())} total")
            return limited_products

        except Exception as e:
            logger.warning(f"Could not load product names: {e}")
            return {"power_source": [], "feeder": [], "cooler": []}

    async def extract_parameters(
        self,
        user_message: str,
        current_state: str,
        master_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract parameters from user message using LLM
        Returns complete updated MasterParameterJSON

        Args:
            user_message: User's natural language input
            current_state: Current state (e.g., "power_source_selection")
            master_parameters: Existing MasterParameterJSON dict

        Returns:
            Updated complete MasterParameterJSON dict
        """

        try:
            logger.info(f"Extracting parameters for state: {current_state}")

            # Build extraction prompt based on current state
            prompt = self._build_extraction_prompt(
                user_message,
                current_state,
                master_parameters
            )

            # Call OpenAI for parameter extraction
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a welding equipment expert. Extract technical parameters from user queries into component-based JSON structure."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            # Parse LLM response
            extracted_text = response.choices[0].message.content
            updated_master = self._parse_llm_response(extracted_text, master_parameters)

            logger.info(f"Extraction complete. Updated components: {list(updated_master.keys())}")
            return updated_master

        except Exception as e:
            logger.error(f"Parameter extraction failed: {e}")

            # Return unchanged master_parameters on error
            return master_parameters

    def _build_extraction_prompt(
        self,
        user_message: str,
        current_state: str,
        master_parameters: Dict[str, Any]
    ) -> str:
        """Build extraction prompt with product name knowledge"""

        # State-specific extraction guidance
        state_guidance = {
            "power_source_selection": """
FOCUS: Extract requirements for POWER SOURCE component
Look for: process type, current rating, voltage, material, application, environment, duty cycle
Product Names: If user mentions specific power source models, add to power_source.product_name
""",
            "feeder_selection": """
FOCUS: Extract requirements for FEEDER component
Look for: process type, material, thickness, cooling type, wire diameter
Product Names: If user mentions specific feeder models, add to feeder.product_name
""",
            "cooler_selection": """
FOCUS: Extract requirements for COOLER component
Look for: duty cycle, application, environment, cooling capacity
Product Names: If user mentions specific cooler models, add to cooler.product_name
""",
            "interconnector_selection": """
FOCUS: Extract requirements for INTERCONNECTOR component
Look for: cable length, current rating, cooling type (gas/liquid), cross-section
""",
            "torch_selection": """
FOCUS: Extract requirements for TORCH component
Look for: process type, current rating, cooling type, swan neck angle
""",
            "accessories_selection": """
FOCUS: Extract requirements for ACCESSORIES component
Look for: accessory type, compatibility, cable length, remote control features
"""
        }

        # Get state-specific guidance
        guidance = state_guidance.get(current_state, "Extract any welding-related requirements")

        # Build product name reference (only for PowerSource, Feeder, Cooler)
        product_reference = ""
        if self.product_names:
            product_reference = "\n\nKNOWN PRODUCT NAMES (for reference):\n"

            if self.product_names.get("power_source"):
                product_reference += f"\nPower Sources:\n"
                product_reference += "\n".join([f"  - {name}" for name in self.product_names["power_source"][:10]])
                if len(self.product_names["power_source"]) > 10:
                    product_reference += f"\n  ... and {len(self.product_names['power_source']) - 10} more"

            if self.product_names.get("feeder"):
                product_reference += f"\n\nFeeders:\n"
                product_reference += "\n".join([f"  - {name}" for name in self.product_names["feeder"][:10]])
                if len(self.product_names["feeder"]) > 10:
                    product_reference += f"\n  ... and {len(self.product_names['feeder']) - 10} more"

            if self.product_names.get("cooler"):
                product_reference += f"\n\nCoolers:\n"
                product_reference += "\n".join([f"  - {name}" for name in self.product_names["cooler"][:10]])
                if len(self.product_names["cooler"]) > 10:
                    product_reference += f"\n  ... and {len(self.product_names['cooler']) - 10} more"

        # Filter out datetime fields for JSON serialization
        serializable_params = {
            k: v for k, v in master_parameters.items()
            if k != "last_updated" and not isinstance(v, type(master_parameters.get("last_updated")))
        }

        # Build full prompt
        prompt = f"""
TASK: Extract welding equipment requirements from user query and update the Master Parameter JSON.

USER QUERY: "{user_message}"

CURRENT STATE: {current_state}

{guidance}

EXISTING MASTER PARAMETER JSON:
{json.dumps(serializable_params, indent=2)}
{product_reference}

INSTRUCTIONS:
1. COMPONENT-BASED EXTRACTION:
   - Each component (power_source, feeder, cooler, interconnector, torch, accessories) has its own dict
   - Extract requirements into the appropriate component dict based on current state
   - Use string keys and string values (e.g., {{"current_output": "500 A", "process": "MIG (GMAW)"}})

2. PRODUCT NAME RECOGNITION:
   - If user mentions a specific product name from the list above, add it to the component's dict
   - Use key "product_name" (e.g., {{"product_name": "Aristo 500ix"}})
   - Match product names to correct component category

3. COMPOUND REQUESTS:
   - User might mention requirements for multiple components in one message
   - Example: "I want 500A power source with water cooled feeder"
   - Extract both: power_source {{"current_output": "500 A"}} AND feeder {{"cooling_type": "water-cooled"}}

4. PRESERVE EXISTING VALUES:
   - Start with the existing Master Parameter JSON
   - Only update/add new information from current user query
   - Do NOT remove or nullify existing values unless user explicitly changes them

5. FEATURE EXTRACTION EXAMPLES:
   - "500A MIG welder" → power_source: {{"current_output": "500 A", "process": "MIG (GMAW)"}}
   - "aluminum 6mm thick" → power_source or feeder: {{"material": "Aluminum", "thickness": "6 mm"}}
   - "water cooled feeder" → feeder: {{"cooling_type": "Water-cooled"}}
   - "Aristo 500ix" → power_source: {{"product_name": "Aristo 500ix"}}
   - "RobustFeed with Cool2" → feeder: {{"product_name": "RobustFeed"}}, cooler: {{"product_name": "Cool2"}}

6. OUTPUT FORMAT:
   - Return COMPLETE updated Master Parameter JSON
   - Include ALL components (power_source, feeder, cooler, interconnector, torch, accessories)
   - Use empty dict {{}} for components with no requirements

RETURN COMPLETE UPDATED JSON:
{{
  "power_source": {{...}},
  "feeder": {{...}},
  "cooler": {{...}},
  "interconnector": {{...}},
  "torch": {{...}},
  "accessories": {{...}}
}}
"""
        return prompt

    def _parse_llm_response(
        self,
        llm_response: str,
        fallback_master: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse LLM JSON response into MasterParameterJSON dict"""

        import re

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in LLM response")

            # Parse JSON
            parsed_data = json.loads(json_str)

            # Validate structure - ensure all components exist (from schema)
            required_components = get_component_list()
            for component in required_components:
                if component not in parsed_data:
                    parsed_data[component] = {}

            logger.info(f"Successfully parsed LLM response with {sum(len(v) for v in parsed_data.values() if isinstance(v, dict))} total features")
            return parsed_data

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"LLM response was: {llm_response}")

            # Return fallback master_parameters unchanged
            return fallback_master


# Dependency injection
_parameter_extractor = None

async def get_parameter_extractor(openai_api_key: str) -> ParameterExtractor:
    """Get singleton parameter extractor instance"""
    global _parameter_extractor
    if _parameter_extractor is None:
        _parameter_extractor = ParameterExtractor(openai_api_key)
    return _parameter_extractor
