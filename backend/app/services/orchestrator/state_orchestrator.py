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
            message = await self.message_generator.generate_no_results_message(
                ConfiguratorState.POWER_SOURCE_SELECTION.value,
                conversation_state.language
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
            # Try to find matching products
            logger.info(f"User explicitly requested product: {explicit_name}")

            matching_products = []
            for product in search_results.products:
                # Normalize both names: remove spaces, lowercase
                normalized_explicit = explicit_name.lower().replace(" ", "")
                normalized_product = product.name.lower().replace(" ", "")

                # Check if either contains the other (flexible matching)
                if normalized_explicit in normalized_product or normalized_product in normalized_explicit:
                    matching_products.append(product)
                    logger.info(f"Found matching product: {product.name} (GIN: {product.gin})")

            # If exactly ONE match, auto-select it
            if len(matching_products) == 1:
                matching_product = matching_products[0]
                logger.info(f"Single exact match found - auto-selecting: {matching_product.name}")

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

                    # Try to get proactive suggestions for next state
                    proactive_results = await self._get_proactive_suggestions(
                        conversation_state,
                        next_state,
                        limit=3
                    )

                    if proactive_results and proactive_results.products:
                        # Use centralized method for proactive product display (SINGLE METHOD FOR ALL STATES)
                        return self._build_product_selection_response(
                            state=next_state,
                            products=[p.dict() for p in proactive_results.products],
                            prefix_message=f"{confirmation}\n\n",
                            is_proactive=True,
                            product_selected=True,
                            auto_selected=True
                        )
                    else:
                        # No proactive suggestions available, generate normal prompt
                        next_prompt = await self.message_generator.generate_state_prompt(
                            next_state.value,
                            conversation_state.master_parameters.dict(),
                            self._serialize_response_json(conversation_state),
                            conversation_state.language
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

            # If MULTIPLE matches found, show all options to user for selection
            elif len(matching_products) > 1:
                logger.info(f"Multiple matches found ({len(matching_products)}) - showing all options to user")
                # Fall through to show all search results

            # If NO matches found, also fall through to show all search results
            else:
                logger.warning(f"No exact match found for '{explicit_name}' - showing all available options")

        # Agent 3: Return products with standardized message (SINGLE METHOD FOR ALL STATES)
        return self._build_product_selection_response(
            state=ConfiguratorState.POWER_SOURCE_SELECTION,
            products=[p.dict() for p in search_results.products],
            prefix_message="",
            is_proactive=False
        )

    async def _process_component_selection(
        self,
        conversation_state: ConversationState,
        component_type: str
    ) -> Dict[str, Any]:
        """
        S2-S5: Component Selection with Compatibility Validation
        Includes product name validation for Feeder and Cooler
        """

        # Check if product name was already specified in initial compound request
        # (before we even search for products)
        master_params_dict = conversation_state.master_parameters.dict()
        component_key = component_type.lower()
        component_dict = master_params_dict.get(component_key, {})
        pre_existing_name = component_dict.get("product_name")

        if pre_existing_name:
            logger.info(f"Found pre-existing {component_type} product name from compound request: {pre_existing_name}")

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

        # Log response_json for debugging
        serialized_response = self._serialize_response_json(conversation_state)
        logger.info(f"response_json before {component_type} search: {serialized_response}")

        # Agent 2: Search for compatible products
        search_results = await search_method(
            master_params_dict,
            serialized_response
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

        # Use pre-existing product name if it exists (from compound request)
        # This handles cases where user says "I want Aristo 500 with RobustFeed and Cool2"
        # The feeder/cooler names are preserved in master_parameters across state transitions
        explicit_name = pre_existing_name

        if explicit_name:
            logger.info(f"User explicitly requested {component_type}: {explicit_name}")

            # Try to find matching products
            matching_products = []
            for product in search_results.products:
                normalized_explicit = explicit_name.lower().replace(" ", "")
                normalized_product = product.name.lower().replace(" ", "")

                if normalized_explicit in normalized_product or normalized_product in normalized_explicit:
                    matching_products.append(product)
                    logger.info(f"Found matching {component_type}: {product.name} (GIN: {product.gin})")

            # If exactly ONE match, auto-select it
            if len(matching_products) == 1:
                matching_product = matching_products[0]
                logger.info(f"Single exact match found - auto-selecting: {matching_product.name}")

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

                    # Try to get proactive suggestions for next state
                    proactive_results = await self._get_proactive_suggestions(
                        conversation_state,
                        next_state,
                        limit=3
                    )

                    if proactive_results and proactive_results.products:
                        # Use centralized method for proactive product display (SINGLE METHOD FOR ALL STATES)
                        return self._build_product_selection_response(
                            state=next_state,
                            products=[p.dict() for p in proactive_results.products],
                            prefix_message=f"{confirmation}\n\n",
                            is_proactive=True,
                            product_selected=True,
                            auto_selected=True
                        )
                    else:
                        # No proactive suggestions available, generate normal prompt
                        next_prompt = await self.message_generator.generate_state_prompt(
                            next_state.value,
                            conversation_state.master_parameters.dict(),
                            self._serialize_response_json(conversation_state),
                            conversation_state.language
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

            # If MULTIPLE matches found, show all options to user for selection
            elif len(matching_products) > 1:
                logger.info(f"Multiple matches found ({len(matching_products)}) - showing all options to user")
                # Fall through to show all search results

            # If NO matches found, also fall through to show all search results
            else:
                logger.warning(f"No exact match found for '{explicit_name}' - showing all available options")

        # Agent 3: Return products with standardized message (SINGLE METHOD FOR ALL STATES)
        return self._build_product_selection_response(
            state=conversation_state.current_state,
            products=[p.dict() for p in search_results.products],
            prefix_message="",
            is_proactive=False
        )

    async def _process_accessories_selection(
        self,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """
        S6: Accessories Selection
        """

        # Search for accessories - LLM will determine specific category from accessory_type
        search_results = await self.product_search.search_accessories(
            conversation_state.master_parameters.dict(),
            self._serialize_response_json(conversation_state)
            # No default category - let LLM-extracted accessory_type be used
        )

        if not search_results.products:
            # No accessories found - can skip to finalize
            message = "No accessories found. Say 'done' to finalize your configuration."
            return {
                "message": message,
                "current_state": ConfiguratorState.ACCESSORIES_SELECTION.value,
                "products": []
            }

        # Agent 3: Return products with standardized message (SINGLE METHOD FOR ALL STATES)
        return self._build_product_selection_response(
            state=ConfiguratorState.ACCESSORIES_SELECTION,
            products=[p.dict() for p in search_results.products],
            prefix_message="",
            is_proactive=False
        )

    async def _process_finalize(
        self,
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """
        S7: Finalize Configuration
        """

        # Check if can finalize (PowerSource required)
        if not conversation_state.can_finalize():
            message = self.message_generator.generate_error_message(
                "invalid_selection",
                "PowerSource is required. Please select a power source first."
            )
            return {
                "message": message,
                "current_state": ConfiguratorState.FINALIZE.value,
                "can_finalize": False
            }

        # Generate finalization message
        message = await self.message_generator.generate_state_prompt(
            ConfiguratorState.FINALIZE.value,
            conversation_state.master_parameters.dict(),
            self._serialize_response_json(conversation_state),
            conversation_state.language
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

        # Cannot skip PowerSource - it's mandatory
        if conversation_state.current_state == ConfiguratorState.POWER_SOURCE_SELECTION:
            message = self.message_generator.generate_error_message(
                "power_source_required",
                "PowerSource selection is mandatory and cannot be skipped."
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
            next_prompt = await self.message_generator.generate_state_prompt(
                next_state.value,
                conversation_state.master_parameters.dict(),
                self._serialize_response_json(conversation_state),
                conversation_state.language
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

    def _build_product_selection_response(
        self,
        state: ConfiguratorState,
        products: list,
        prefix_message: str = "",
        is_proactive: bool = False,
        custom_prompt: str = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """
        SINGLE method to build product selection response for ALL states

        Args:
            state: Current configurator state
            products: List of products to display as tiles
            prefix_message: Message to show before product options (confirmation, config summary, etc.)
            is_proactive: Whether these are proactive suggestions or search results
            custom_prompt: Optional custom prompt to override default selection prompt
            additional_fields: Any additional response fields (product_selected, auto_selected, etc.)

        Returns:
            Standardized response dict with message and products
        """

        state_names = {
            ConfiguratorState.POWER_SOURCE_SELECTION: "Power Source",
            ConfiguratorState.FEEDER_SELECTION: "Wire Feeder",
            ConfiguratorState.COOLER_SELECTION: "Cooling System",
            ConfiguratorState.INTERCONNECTOR_SELECTION: "Interconnector",
            ConfiguratorState.TORCH_SELECTION: "Torch",
            ConfiguratorState.ACCESSORIES_SELECTION: "Accessories"
        }

        component_name = state_names.get(state, state.value.replace("_", " ").title())
        product_count = len(products)

        # Use custom prompt if provided, otherwise build default
        if custom_prompt:
            selection_prompt = f"\n\n📋 **{state.value.replace('_', ' ').title()}**\n\n"
            selection_prompt += f"Here are {product_count} compatible {component_name} options:\n\n"
            selection_prompt += custom_prompt
        else:
            # Build the product selection prompt
            if is_proactive:
                selection_prompt = f"\n\n📋 **{state.value.replace('_', ' ').title()}**\n\n"
                selection_prompt += f"Here are {product_count} compatible {component_name} options based on your selection:\n\n"
            else:
                selection_prompt = f"\n\n📋 **{state.value.replace('_', ' ').title()}**\n\n"
                selection_prompt += f"I found {product_count} {component_name} option{'s' if product_count != 1 else ''} for you:\n\n"

            selection_prompt += "You can:\n"
            selection_prompt += "- ✅ Select from these options below\n"
            selection_prompt += "- 🔍 Provide specific requirements to search for other options\n"
            selection_prompt += "- ⏭️ Say 'skip' if not needed"

        # Combine prefix message with selection prompt
        full_message = prefix_message + selection_prompt if prefix_message else selection_prompt

        # Build standardized response
        response = {
            "message": full_message,
            "current_state": state.value,
            "products": products,
            "awaiting_selection": True
        }

        # Add any additional fields
        if is_proactive:
            response["proactive_suggestions"] = True

        response.update(additional_fields)

        return response

    def _generate_proactive_message(self, next_state: ConfiguratorState, product_count: int) -> str:
        """Generate message for proactive product suggestions"""

        state_names = {
            ConfiguratorState.FEEDER_SELECTION: "Wire Feeder",
            ConfiguratorState.COOLER_SELECTION: "Cooling System",
            ConfiguratorState.INTERCONNECTOR_SELECTION: "Interconnector",
            ConfiguratorState.TORCH_SELECTION: "Torch",
            ConfiguratorState.ACCESSORIES_SELECTION: "Accessories"
        }

        component_name = state_names.get(next_state, next_state.value.replace("_", " ").title())

        message = f"📋 **{next_state.value.replace('_', ' ').title()}**\n\n"
        message += f"Here are {product_count} compatible {component_name} options based on your selection:\n\n"
        message += "You can:\n"
        message += "- ✅ Select from these options below\n"
        message += "- 🔍 Provide specific requirements to search for other options\n"
        message += "- ⏭️ Say 'skip' if not needed"

        return message

    async def _get_proactive_suggestions(
        self,
        conversation_state: ConversationState,
        next_state: ConfiguratorState,
        limit: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Proactively search for top N products for next state
        Uses existing selected products for compatibility validation

        Args:
            conversation_state: Current conversation state
            next_state: The state we're moving to
            limit: Number of products to return (default 3)

        Returns:
            SearchResults with top N products, or None if no search needed
        """

        # Map state to search method
        search_methods = {
            ConfiguratorState.FEEDER_SELECTION: self.product_search.search_feeder,
            ConfiguratorState.COOLER_SELECTION: self.product_search.search_cooler,
            ConfiguratorState.INTERCONNECTOR_SELECTION: self.product_search.search_interconnector,
            ConfiguratorState.TORCH_SELECTION: self.product_search.search_torch,
            ConfiguratorState.ACCESSORIES_SELECTION: self.product_search.search_accessories
        }

        search_method = search_methods.get(next_state)
        if not search_method:
            logger.debug(f"No search method for state: {next_state}")
            return None  # FINALIZE or unknown state

        # Get current master parameters (may be empty for next component)
        master_params = conversation_state.master_parameters.dict()

        # Get selected products for compatibility validation
        response_json = self._serialize_response_json(conversation_state)

        # Perform search with existing parameters
        try:
            logger.info(f"Performing proactive search for {next_state} (limit: {limit})")

            if next_state == ConfiguratorState.ACCESSORIES_SELECTION:
                search_results = await search_method(
                    master_params,
                    response_json,
                    None  # Search all accessory categories (PowerSourceAccessory, FeederAccessory, etc.)
                )
            else:
                search_results = await search_method(
                    master_params,
                    response_json
                )

            # Limit to top N products
            if search_results.products:
                original_count = len(search_results.products)
                if original_count > limit:
                    search_results.products = search_results.products[:limit]
                    logger.info(f"Limited proactive results from {original_count} to {limit} products")
                else:
                    logger.info(f"Proactive search returned {original_count} products")

                return search_results
            else:
                logger.info(f"No products found in proactive search for {next_state}")
                return None

        except Exception as e:
            logger.warning(f"Proactive search failed for {next_state}: {e}")
            return None

    async def select_product(
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
            logger.info("=" * 80)
            logger.info("🔍 ORCHESTRATOR: Loading applicability for PowerSource")
            logger.info(f"Product GIN: {product_gin}")
            logger.info(f"Product Name: {selected_product.name}")

            applicability = self._get_component_applicability(product_gin)

            logger.info(f"Loaded applicability: {applicability}")
            if applicability:
                logger.info(f"  Feeder: {applicability.Feeder}")
                logger.info(f"  Cooler: {applicability.Cooler}")
                logger.info(f"  Interconnector: {applicability.Interconnector}")
                logger.info(f"  Torch: {applicability.Torch}")
                logger.info(f"  Accessories: {applicability.Accessories}")

            conversation_state.set_applicability(applicability)
            logger.info("=" * 80)

        else:
            # Select other components
            conversation_state.select_component(component_type, selected_product)

        # Generate confirmation
        confirmation = self.message_generator.generate_selection_confirmation(
            component_type,
            selected_product.name,
            selected_product.gin
        )

        # Generate current configuration summary
        config_summary = self._generate_config_summary(conversation_state)

        # For Accessories, allow multiple selections - stay in current state
        if conversation_state.current_state == ConfiguratorState.ACCESSORIES_SELECTION:
            # Perform proactive search for more accessories (excluding already selected ones)
            proactive_results = await self._get_proactive_suggestions(
                conversation_state,
                ConfiguratorState.ACCESSORIES_SELECTION,
                limit=10  # Show more accessories since they can select multiple
            )

            prefix_message = f"{confirmation}\n\n{config_summary}\n\n"

            if proactive_results and proactive_results.products:
                # Return products for selection
                return self._build_product_selection_response(
                    state=ConfiguratorState.ACCESSORIES_SELECTION,
                    products=[p.dict() for p in proactive_results.products],
                    prefix_message=prefix_message,
                    is_proactive=True,
                    product_selected=True,
                    custom_prompt=(
                        "Would you like to:\n"
                        "- Add another accessory (select from the options below)\n"
                        "- Say 'done' to finalize your configuration"
                    )
                )
            else:
                # No more accessories available
                message = f"{prefix_message}"
                message += "Would you like to:\n"
                message += "- Add another accessory (provide specific requirements to search)\n"
                message += "- Say 'done' to finalize your configuration"

                return {
                    "message": message,
                    "current_state": conversation_state.current_state.value,
                    "product_selected": True,
                    "stay_in_state": True
                }

        # For other components, move to next state
        logger.info("🔍 ORCHESTRATOR: Calling get_next_state()")
        next_state = conversation_state.get_next_state()
        logger.info(f"🔍 ORCHESTRATOR: get_next_state() returned: {next_state.value if next_state else None}")

        if next_state:
            conversation_state.current_state = next_state

            # Try to get proactive suggestions for next state
            proactive_results = await self._get_proactive_suggestions(
                conversation_state,
                next_state,
                limit=3
            )

            if proactive_results and proactive_results.products:
                # Use centralized method for proactive product display (SINGLE METHOD FOR ALL STATES)
                return self._build_product_selection_response(
                    state=next_state,
                    products=[p.dict() for p in proactive_results.products],
                    prefix_message=f"{confirmation}\n\n{config_summary}\n\n",
                    is_proactive=True,
                    product_selected=True
                )
            else:
                # No proactive suggestions available, generate normal prompt
                next_prompt = await self.message_generator.generate_state_prompt(
                    next_state.value,
                    conversation_state.master_parameters.dict(),
                    self._serialize_response_json(conversation_state),
                    conversation_state.language
                )

                message = f"{confirmation}\n\n{config_summary}\n\n{next_prompt}"
        else:
            message = f"{confirmation}\n\n{config_summary}"

        return {
            "message": message,
            "current_state": conversation_state.current_state.value,
            "product_selected": True
        }

    def _get_component_applicability(self, power_source_gin: str) -> ComponentApplicability:
        """Load component applicability from config for power source by GIN"""

        power_sources = self.applicability_config.get("power_sources", {})
        ps_config = power_sources.get(power_source_gin)

        if ps_config:
            logger.info(f"✅ Found applicability config for GIN: {power_source_gin}")
            applicability_data = ps_config.get("applicability", {})
            return ComponentApplicability(**applicability_data)
        else:
            # Use default policy
            logger.warning(f"⚠️ No applicability config found for GIN: {power_source_gin}, using defaults")
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

    def _generate_config_summary(self, conversation_state: ConversationState) -> str:
        """Generate current configuration summary for display in chat"""

        summary = "📋 **Current Configuration:**\n\n"

        # PowerSource - always show
        if conversation_state.response_json.PowerSource:
            ps = conversation_state.response_json.PowerSource
            summary += f"✅ **PowerSource**: {ps.name} (GIN: {ps.gin})\n"

        # Only show other components if they've been selected (not None)
        # This prevents showing "Skipped" for components not yet encountered

        if conversation_state.response_json.Feeder:
            feeder = conversation_state.response_json.Feeder
            summary += f"✅ **Feeder**: {feeder.name} (GIN: {feeder.gin})\n"

        if conversation_state.response_json.Cooler:
            cooler = conversation_state.response_json.Cooler
            summary += f"✅ **Cooler**: {cooler.name} (GIN: {cooler.gin})\n"

        if conversation_state.response_json.Interconnector:
            ic = conversation_state.response_json.Interconnector
            summary += f"✅ **Interconnector**: {ic.name} (GIN: {ic.gin})\n"

        if conversation_state.response_json.Torch:
            torch = conversation_state.response_json.Torch
            summary += f"✅ **Torch**: {torch.name} (GIN: {torch.gin})\n"

        if conversation_state.response_json.Accessories:
            summary += f"✅ **Accessories** ({len(conversation_state.response_json.Accessories)}):\n"
            for acc in conversation_state.response_json.Accessories:
                summary += f"   • {acc.name} (GIN: {acc.gin})\n"

        return summary
