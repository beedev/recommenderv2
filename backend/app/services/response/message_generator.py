"""
Simplified Response Generator for S1→S7 Flow
Generates user-friendly messages based on current state
"""

import logging
from typing import Dict, List, Optional, Any
from ..neo4j.product_search import SearchResults

logger = logging.getLogger(__name__)


class MessageGenerator:
    """
    Simple message generator for conversational responses
    Tailored to S1→S7 state-by-state flow
    """

    def __init__(self):
        """Initialize message generator"""
        logger.info("Message Generator initialized")

    def generate_state_prompt(
        self,
        current_state: str,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """
        Generate prompt message for current state
        Guides user through S1→S7 selection process
        """

        # State-specific prompts
        state_prompts = {
            "power_source_selection": self._prompt_power_source,
            "feeder_selection": self._prompt_feeder,
            "cooler_selection": self._prompt_cooler,
            "interconnector_selection": self._prompt_interconnector,
            "torch_selection": self._prompt_torch,
            "accessories_selection": self._prompt_accessories,
            "finalize": self._prompt_finalize
        }

        # Get state-specific prompt generator
        prompt_generator = state_prompts.get(current_state, self._prompt_default)

        # Generate prompt
        return prompt_generator(master_parameters, response_json)

    def generate_search_results_message(
        self,
        current_state: str,
        search_results: SearchResults,
        master_parameters: Dict[str, Any]
    ) -> str:
        """
        Generate message presenting search results to user
        """

        if not search_results.products:
            return self._generate_no_results_message(current_state)

        # Build results message
        component_name = self._get_component_name(current_state)

        message = f"I found {search_results.total_count} {component_name} options"

        # Add compatibility note if validated
        if search_results.compatibility_validated:
            message += " that are compatible with your selected components"

        message += ":\n\n"

        # List products
        for idx, product in enumerate(search_results.products[:5], 1):  # Show top 5
            message += f"{idx}. **{product.name}** (GIN: {product.gin})\n"
            if product.description:
                message += f"   {product.description}\n"

        # Add selection instruction
        message += f"\n✅ To select a {component_name}, please provide:"
        message += "\n- Product name or GIN"
        message += "\n- Or say 'skip' if not needed"

        return message

    def generate_selection_confirmation(
        self,
        component_type: str,
        product_name: str,
        product_gin: str
    ) -> str:
        """Generate confirmation message for product selection"""

        return f"✅ Selected **{product_name}** (GIN: {product_gin}) for {component_type}."

    def generate_skip_confirmation(self, component_type: str) -> str:
        """Generate confirmation message for skipping a component"""

        return f"⏭️ Skipping {component_type} selection."

    def generate_error_message(self, error_type: str, details: str = "") -> str:
        """Generate user-friendly error messages"""

        error_messages = {
            "power_source_required": "⚠️ PowerSource selection is mandatory. Please provide your welding requirements or select a specific power source.",
            "invalid_selection": f"⚠️ Invalid selection. {details}",
            "search_failed": "⚠️ Product search failed. Please try again or rephrase your request.",
            "compatibility_failed": f"⚠️ No compatible products found. {details}"
        }

        return error_messages.get(error_type, f"⚠️ An error occurred: {details}")

    # Private helper methods for state-specific prompts

    def _prompt_power_source(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Prompt for S1: PowerSource (MANDATORY)"""

        return """
🔋 **Step 1: Power Source Selection (Required)**

Please tell me about your welding needs:
- What welding process? (MIG, TIG, STICK, etc.)
- Required amperage or power range?
- Application type? (industrial, automotive, construction, etc.)
- Any specific model in mind?

This is a required step - I'll help you find the right power source.
"""

    def _prompt_feeder(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Prompt for S2: Feeder"""

        power_source = response_json.get("PowerSource", {})

        return f"""
🔌 **Step 2: Wire Feeder Selection**

Based on your selected power source: **{power_source.get('name', 'Unknown')}**

Do you need a wire feeder?
- Provide requirements (portability, wire feed speed, etc.)
- Or say **'skip'** if not needed
"""

    def _prompt_cooler(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Prompt for S3: Cooler"""

        return """
❄️ **Step 3: Cooling System Selection**

Do you need a cooling system?
- Specify cooling requirements (duty cycle, flow rate, etc.)
- Or say **'skip'** if not needed
"""

    def _prompt_interconnector(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Prompt for S4: Interconnector"""

        return """
🔗 **Step 4: Interconnector Cable Selection**

Do you need interconnector cables?
- Specify length and current rating requirements
- Or say **'skip'** if not needed
"""

    def _prompt_torch(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Prompt for S5: Torch"""

        return """
🔦 **Step 5: Welding Torch Selection**

Do you need a welding torch?
- Specify torch type (TIG/MIG), current rating, cooling type
- Or say **'skip'** if not needed
"""

    def _prompt_accessories(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Prompt for S6: Accessories"""

        return """
🛠️ **Step 6: Accessories Selection**

Do you need any accessories?
- Power source accessories
- Connectivity accessories
- Remote controls
- Other accessories

Or say **'done'** to finalize your configuration.
"""

    def _prompt_finalize(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Prompt for S7: Finalize"""

        # Count selected components
        selected_components = [k for k, v in response_json.items() if v and k != "session_id"]

        summary = "📋 **Configuration Summary:**\n\n"

        for component_type, component_data in response_json.items():
            if component_type == "session_id":
                continue

            if component_data:
                summary += f"- **{component_type}**: {component_data.get('name', 'Selected')}\n"

        summary += f"\n✅ Total components selected: {len(selected_components)}\n"

        if len(selected_components) >= 3:
            summary += "\n✨ Your configuration is ready! Would you like to:"
            summary += "\n1. Review component details"
            summary += "\n2. Make changes"
            summary += "\n3. Confirm and generate packages"
        else:
            summary += f"\n⚠️ Minimum 3 components required (currently: {len(selected_components)})"
            summary += "\nPlease add more components to complete your configuration."

        return summary

    def _prompt_default(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """Default prompt for unknown states"""

        return "How can I help you with your welding equipment configuration?"

    def _get_component_name(self, state: str) -> str:
        """Get friendly component name from state"""

        component_names = {
            "power_source_selection": "Power Source",
            "feeder_selection": "Wire Feeder",
            "cooler_selection": "Cooling System",
            "interconnector_selection": "Interconnector Cable",
            "torch_selection": "Welding Torch",
            "accessories_selection": "Accessory"
        }

        return component_names.get(state, "Component")

    def _generate_no_results_message(self, current_state: str) -> str:
        """Generate message when no search results found"""

        component_name = self._get_component_name(current_state)

        return f"""
⚠️ No {component_name} options found matching your requirements.

This could mean:
- No compatible products available
- Requirements may need adjustment
- Or you can skip this component

Would you like to:
1. Adjust your requirements
2. Skip this component
3. Get help from a specialist
"""


# Dependency injection
_message_generator = None

def get_message_generator() -> MessageGenerator:
    """Get singleton message generator instance"""
    global _message_generator
    if _message_generator is None:
        _message_generator = MessageGenerator()
    return _message_generator
