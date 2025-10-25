"""
State-by-State Orchestrator for S1→S7 Flow
Coordinates the 3 agents and manages state progression
"""

import logging
import json
from typing import Dict, Any, Optional
from ...models.conversation import (
    ConversationState,
    ConfiguratorState,
    ComponentApplicability,
    SelectedProduct
)
from ..intent.parameter_extractor import ParameterExtractor
from ..neo4j.product_search import Neo4jProductSearch
from ..response.message_generator import MessageGenerator

logger = logging.getLogger(__name__)


class StateByStateOrchestrator:
    """
    Orchestrates S1→S7 state-by-state configuration flow
    Coordinates: Parameter Extraction → Product Search → Response Generation
    """

    def __init__(
        self,
        parameter_extractor: ParameterExtractor,
        product_search: Neo4jProductSearch,
        message_generator: MessageGenerator,
        component_applicability_config: Dict[str, Any]
    ):
        """Initialize orchestrator with all 3 agents"""
        self.parameter_extractor = parameter_extractor
        self.product_search = product_search
        self.message_generator = message_generator
        self.applicability_config = component_applicability_config

        logger.info("State-by-State Orchestrator initialized")

    async def process_message(
        self,
        conversation_state: ConversationState,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process user message in current state
        Returns response with updated state and message
        """

        try:
            logger.info(f"Processing message in state: {conversation_state.current_state}")

            # Add user message to history
            conversation_state.add_message("user", user_message)

            # Check for special commands first
            if user_message.lower().strip() == "skip":
                return await self._handle_skip(conversation_state)

            if user_message.lower().strip() in ["done", "finish", "finalize"]:
                return await self._handle_finalize(conversation_state)

            # Agent 1: Extract parameters from user message
            # Returns complete updated MasterParameterJSON dict
            updated_master = await self.parameter_extractor.extract_parameters(
                user_message,
                conversation_state.current_state.value,
                conversation_state.master_parameters.dict()
            )
            conversation_state.update_master_parameters(updated_master)

            # Process based on current state
            if conversation_state.current_state == ConfiguratorState.POWER_SOURCE_SELECTION:
                response = await self._process_power_source_selection(conversation_state)

            elif conversation_state.current_state == ConfiguratorState.FEEDER_SELECTION:
                response = await self._process_component_selection(conversation_state, "Feeder")

            elif conversation_state.current_state == ConfiguratorState.COOLER_SELECTION:
                response = await self._process_component_selection(conversation_state, "Cooler")

            elif conversation_state.current_state == ConfiguratorState.INTERCONNECTOR_SELECTION:
                response = await self._process_component_selection(conversation_state, "Interconnector")

            elif conversation_state.current_state == ConfiguratorState.TORCH_SELECTION:
                response = await self._process_component_selection(conversation_state, "Torch")

            elif conversation_state.current_state == ConfiguratorState.ACCESSORIES_SELECTION:
                response = await self._process_accessories_selection(conversation_state)

            elif conversation_state.current_state == ConfiguratorState.FINALIZE:
                response = await self._process_finalize(conversation_state)

            else:
                response = {
                    "message": "Unknown state. Please restart the configuration.",
                    "error": True
                }

            # Add assistant message to history
            conversation_state.add_message("assistant", response.get("message", ""))

            return response

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_message = self.message_generator.generate_error_message(
                "search_failed",
                str(e)
            )
            return {
                "message": error_message,
                "error": True,
                "current_state": conversation_state.current_state.value
            }

    async def _process_power_source_selection(
        self,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """
        S1: PowerSource Selection (MANDATORY)
        Cannot skip this state
        """

        # Agent 2: Search for power sources
        master_params_dict = conversation_state.master_parameters.dict()
        logger.info(f"Master parameters before search: {master_params_dict}")

        search_results = await self.product_search.search_power_source(
            master_params_dict
        )

        if not search_results.products:
            # No results - prompt user for more information
            message = self.message_generator.generate_error_message(
                "power_source_required",
                "Please provide more details about your welding requirements."
            )
            return {
                "message": message,
                "current_state": ConfiguratorState.POWER_SOURCE_SELECTION.value,
                "products": []
            }

        # Check if user explicitly mentioned a product name in power_source component
        power_source_component = master_params_dict.get("power_source", {})
        explicit_name = power_source_component.get("product_name")
        logger.info(f"Checking for explicit power source product name: {explicit_name}")

        if explicit_name:
            # Try to find the exact product by name
            logger.info(f"User explicitly requested product: {explicit_name}")

            matching_product = None
            for product in search_results.products:
                # Normalize both names: remove spaces, lowercase
                normalized_explicit = explicit_name.lower().replace(" ", "")
                normalized_product = product.name.lower().replace(" ", "")

                # Check if either contains the other (flexible matching)
                if normalized_explicit in normalized_product or normalized_product in normalized_explicit:
                    matching_product = product
                    logger.info(f"Found matching product: {product.name} (GIN: {product.gin})")
                    break

            if not matching_product:
                logger.warning(f"No product found matching '{explicit_name}' among {len(search_results.products)} products")

            if matching_product:
                # Auto-select the explicitly mentioned product
                from ...models.conversation import SelectedProduct
                selected_product = SelectedProduct(
                    gin=matching_product.gin,
                    name=matching_product.name,
                    category=matching_product.category,
                    description=matching_product.description,
                    specifications=matching_product.specifications
                )

                # Select power source
                conversation_state.select_component("PowerSource", selected_product)

                # Load and set component applicability
                applicability = self._get_component_applicability(matching_product.gin)
                conversation_state.set_applicability(applicability)

                # Generate confirmation
                confirmation = self.message_generator.generate_selection_confirmation(
                    "PowerSource",
                    selected_product.name,
                    selected_product.gin
                )

                # Move to next state
                next_state = conversation_state.get_next_state()
                if next_state:
                    conversation_state.current_state = next_state

                    # Generate prompt for next state
                    next_prompt = self.message_generator.generate_state_prompt(
                        next_state.value,
                        conversation_state.master_parameters.dict(),
                        self._serialize_response_json(conversation_state)
                    )

                    message = f"{confirmation}\n\n{next_prompt}"
                else:
                    message = confirmation

                return {
                    "message": message,
                    "current_state": conversation_state.current_state.value,
                    "product_selected": True,
                    "auto_selected": True
                }

        # Agent 3: Generate results message (no explicit product or not found)
        message = self.message_generator.generate_search_results_message(
            ConfiguratorState.POWER_SOURCE_SELECTION.value,
            search_results,
            conversation_state.master_parameters.dict()
        )

        return {
            "message": message,
            "current_state": ConfiguratorState.POWER_SOURCE_SELECTION.value,
            "products": [p.dict() for p in search_results.products],
            "awaiting_selection": True
        }

    async def _process_component_selection(
        self,
        conversation_state: ConversationState,
        component_type: str
    ) -> Dict[str, Any]:
        """
        S2-S5: Component Selection with Compatibility Validation
        Includes product name validation for Feeder and Cooler
        """

        # Map component type to search method
        search_methods = {
            "Feeder": self.product_search.search_feeder,
            "Cooler": self.product_search.search_cooler,
            "Interconnector": self.product_search.search_interconnector,
            "Torch": self.product_search.search_torch
        }

        search_method = search_methods.get(component_type)
        if not search_method:
            raise ValueError(f"Unknown component type: {component_type}")

        # Agent 2: Search for compatible products
        master_params_dict = conversation_state.master_parameters.dict()
        search_results = await search_method(
            master_params_dict,
            self._serialize_response_json(conversation_state)
        )

        if not search_results.products:
            message = self.message_generator.generate_error_message(
                "compatibility_failed",
                f"No compatible {component_type} found. Try adjusting requirements or skip."
            )
            return {
                "message": message,
                "current_state": conversation_state.current_state.value,
                "products": []
            }

        # Check for explicit product name (Feeder and Cooler only)
        component_key = component_type.lower()
        component_dict = master_params_dict.get(component_key, {})
        explicit_name = component_dict.get("product_name")

        if explicit_name:
            logger.info(f"User explicitly requested {component_type}: {explicit_name}")

            # Try to find matching product
            matching_product = None
            for product in search_results.products:
                normalized_explicit = explicit_name.lower().replace(" ", "")
                normalized_product = product.name.lower().replace(" ", "")

                if normalized_explicit in normalized_product or normalized_product in normalized_explicit:
                    matching_product = product
                    logger.info(f"Found matching {component_type}: {product.name} (GIN: {product.gin})")
                    break

            if matching_product:
                # Auto-select the explicitly mentioned product
                selected_product = SelectedProduct(
                    gin=matching_product.gin,
                    name=matching_product.name,
                    category=matching_product.category,
                    description=matching_product.description,
                    specifications=matching_product.specifications
                )

                # Select component
                conversation_state.select_component(component_type, selected_product)

                # Generate confirmation
                confirmation = self.message_generator.generate_selection_confirmation(
                    component_type,
                    selected_product.name,
                    selected_product.gin
                )

                # Move to next state
                next_state = conversation_state.get_next_state()
                if next_state:
                    conversation_state.current_state = next_state

                    # Generate prompt for next state
                    next_prompt = self.message_generator.generate_state_prompt(
                        next_state.value,
                        conversation_state.master_parameters.dict(),
                        self._serialize_response_json(conversation_state)
                    )

                    message = f"{confirmation}\n\n{next_prompt}"
                else:
                    message = confirmation

                return {
                    "message": message,
                    "current_state": conversation_state.current_state.value,
                    "product_selected": True,
                    "auto_selected": True
                }

        # Agent 3: Generate results message (no explicit product or not found)
        message = self.message_generator.generate_search_results_message(
            conversation_state.current_state.value,
            search_results,
            conversation_state.master_parameters.dict()
        )

        return {
            "message": message,
            "current_state": conversation_state.current_state.value,
            "products": [p.dict() for p in search_results.products],
            "awaiting_selection": True
        }

    async def _process_accessories_selection(
        self,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """
        S6: Accessories Selection
        """

        # For now, search for general accessories
        search_results = await self.product_search.search_accessories(
            conversation_state.master_parameters.dict(),
            self._serialize_response_json(conversation_state),
            "Accessory"  # Default category
        )

        if not search_results.products:
            # No accessories found - can skip to finalize
            message = "No accessories found. Say 'done' to finalize your configuration."
            return {
                "message": message,
                "current_state": ConfiguratorState.ACCESSORIES_SELECTION.value,
                "products": []
            }

        # Agent 3: Generate results message
        message = self.message_generator.generate_search_results_message(
            conversation_state.current_state.value,
            search_results,
            conversation_state.master_parameters.dict()
        )

        return {
            "message": message,
            "current_state": ConfiguratorState.ACCESSORIES_SELECTION.value,
            "products": [p.dict() for p in search_results.products],
            "awaiting_selection": True
        }

    async def _process_finalize(
        self,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """
        S7: Finalize Configuration
        """

        # Check if can finalize (≥3 components)
        if not conversation_state.can_finalize():
            message = self.message_generator.generate_error_message(
                "invalid_selection",
                "Minimum 3 components required. Please add more components."
            )
            return {
                "message": message,
                "current_state": ConfiguratorState.FINALIZE.value,
                "can_finalize": False
            }

        # Generate finalization message
        message = self.message_generator.generate_state_prompt(
            ConfiguratorState.FINALIZE.value,
            conversation_state.master_parameters.dict(),
            self._serialize_response_json(conversation_state)
        )

        return {
            "message": message,
            "current_state": ConfiguratorState.FINALIZE.value,
            "can_finalize": True,
            "configuration": self._serialize_response_json(conversation_state)
        }

    async def _handle_skip(
        self,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """Handle 'skip' command - move to next state"""

        # Cannot skip PowerSource
        if conversation_state.current_state == ConfiguratorState.POWER_SOURCE_SELECTION:
            message = self.message_generator.generate_error_message(
                "power_source_required"
            )
            return {
                "message": message,
                "current_state": ConfiguratorState.POWER_SOURCE_SELECTION.value
            }

        # Generate skip confirmation
        component_name = self._get_component_name(conversation_state.current_state)
        confirmation = self.message_generator.generate_skip_confirmation(component_name)

        # Move to next state
        next_state = conversation_state.get_next_state()
        if next_state:
            conversation_state.current_state = next_state

            # Generate prompt for next state
            next_prompt = self.message_generator.generate_state_prompt(
                next_state.value,
                conversation_state.master_parameters.dict(),
                self._serialize_response_json(conversation_state)
            )

            message = f"{confirmation}\n\n{next_prompt}"
        else:
            message = confirmation

        return {
            "message": message,
            "current_state": conversation_state.current_state.value,
            "skipped": True
        }

    async def _handle_finalize(
        self,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """Handle 'done' / 'finalize' command"""

        # Move to finalize state
        conversation_state.current_state = ConfiguratorState.FINALIZE

        return await self._process_finalize(conversation_state)

    def select_product(
        self,
        conversation_state: ConversationState,
        product_gin: str,
        product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Select a product for current state component
        Returns next state prompt
        """

        # Create SelectedProduct
        selected_product = SelectedProduct(**product_data)

        # Determine component type from current state
        component_type = self._get_component_type(conversation_state.current_state)

        # Handle S1 PowerSource selection
        if conversation_state.current_state == ConfiguratorState.POWER_SOURCE_SELECTION:
            # Select power source
            conversation_state.select_component(component_type, selected_product)

            # Load and set component applicability
            applicability = self._get_component_applicability(product_gin)
            conversation_state.set_applicability(applicability)

        else:
            # Select other components
            conversation_state.select_component(component_type, selected_product)

        # Generate confirmation
        confirmation = self.message_generator.generate_selection_confirmation(
            component_type,
            selected_product.name,
            selected_product.gin
        )

        # Move to next state
        next_state = conversation_state.get_next_state()
        if next_state:
            conversation_state.current_state = next_state

            # Generate prompt for next state
            next_prompt = self.message_generator.generate_state_prompt(
                next_state.value,
                conversation_state.master_parameters.dict(),
                self._serialize_response_json(conversation_state)
            )

            message = f"{confirmation}\n\n{next_prompt}"
        else:
            message = confirmation

        return {
            "message": message,
            "current_state": conversation_state.current_state.value,
            "product_selected": True
        }

    def _get_component_applicability(self, power_source_gin: str) -> ComponentApplicability:
        """Load component applicability from config for power source"""

        power_sources = self.applicability_config.get("power_sources", {})
        ps_config = power_sources.get(power_source_gin)

        if ps_config:
            applicability_data = ps_config.get("applicability", {})
            return ComponentApplicability(**applicability_data)
        else:
            # Use default policy
            default_policy = self.applicability_config.get("default_policy", {})
            applicability_data = default_policy.get("applicability", {})
            return ComponentApplicability(**applicability_data)

    def _get_component_type(self, state: ConfiguratorState) -> str:
        """Map state to component type"""

        component_map = {
            ConfiguratorState.POWER_SOURCE_SELECTION: "PowerSource",
            ConfiguratorState.FEEDER_SELECTION: "Feeder",
            ConfiguratorState.COOLER_SELECTION: "Cooler",
            ConfiguratorState.INTERCONNECTOR_SELECTION: "Interconnector",
            ConfiguratorState.TORCH_SELECTION: "Torch",
            ConfiguratorState.ACCESSORIES_SELECTION: "Accessories"
        }

        return component_map.get(state, "Unknown")

    def _get_component_name(self, state: ConfiguratorState) -> str:
        """Get friendly component name"""

        return self._get_component_type(state).replace("_", " ")

    def _serialize_response_json(self, conversation_state: ConversationState) -> Dict[str, Any]:
        """Serialize response JSON for Neo4j queries"""

        response_dict = {}

        if conversation_state.response_json.PowerSource:
            response_dict["PowerSource"] = conversation_state.response_json.PowerSource.dict()

        if conversation_state.response_json.Feeder:
            response_dict["Feeder"] = conversation_state.response_json.Feeder.dict()

        if conversation_state.response_json.Cooler:
            response_dict["Cooler"] = conversation_state.response_json.Cooler.dict()

        if conversation_state.response_json.Interconnector:
            response_dict["Interconnector"] = conversation_state.response_json.Interconnector.dict()

        if conversation_state.response_json.Torch:
            response_dict["Torch"] = conversation_state.response_json.Torch.dict()

        if conversation_state.response_json.Accessories:
            response_dict["Accessories"] = [a.dict() for a in conversation_state.response_json.Accessories]

        return response_dict
