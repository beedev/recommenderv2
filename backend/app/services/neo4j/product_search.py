"""
Simplified Neo4j Product Search Service for S1→S7 Flow
Handles component-specific searches with compatibility validation
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from neo4j import AsyncGraphDatabase
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProductResult(BaseModel):
    """Single product search result"""
    gin: str
    name: str
    category: str
    description: Optional[str] = None
    specifications: Dict[str, Any] = {}


class SearchResults(BaseModel):
    """Search results with metadata"""
    products: List[ProductResult]
    total_count: int
    filters_applied: Dict[str, Any]
    compatibility_validated: bool = False


class Neo4jProductSearch:
    """
    Simplified Neo4j product search with compatibility validation
    Focused on S1→S7 component-specific queries
    """

    def __init__(self, uri: str, username: str, password: str):
        """Initialize Neo4j connection"""
        self.driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        self.product_names = self._load_product_names()
        logger.info(f"Neo4j Product Search initialized - URI: {uri}")

    async def close(self):
        """Close Neo4j connection"""
        await self.driver.close()

    def _load_product_names(self) -> Dict[str, List[str]]:
        """
        Load product names from product_names.json
        Only loads PowerSource, Feeder, Cooler for fuzzy matching
        """
        try:
            import os
            import json

            config_path = os.path.join(
                os.path.dirname(__file__),
                "../../config/product_names.json"
            )

            with open(config_path, "r") as f:
                all_products = json.load(f)

            # Only include PowerSource, Feeder, Cooler for fuzzy matching
            limited_products = {
                "power_source": all_products.get("power_source", []),
                "feeder": all_products.get("feeder", []),
                "cooler": all_products.get("cooler", [])
            }

            total_products = sum(len(v) for v in limited_products.values())
            logger.info(f"Loaded {total_products} product names for fuzzy matching")
            return limited_products

        except Exception as e:
            logger.warning(f"Could not load product names: {e}")
            return {"power_source": [], "feeder": [], "cooler": []}

    def _normalize_product_name(self, user_input: str, component_type: str) -> str:
        """
        Fuzzy match user input against known product names
        Returns normalized product name or original input

        Logic:
        - Check how many products in known list start with same first word as user input
        - If multiple products share the same first word: Return first word only
        - If single exact match: Return exact matched product name
        - No match: Return original input

        Args:
            user_input: User's product name input (e.g., "Cool2", "RobustFeed PRO, Water")
            component_type: Component category (power_source, feeder, cooler)

        Returns:
            Normalized product name or first word for multi-match scenarios

        Examples:
            "Cool2" → "COOL 2 Cooling Unit" (single product family)
            "RobustFeed PRO" → "RobustFeed" (multiple RobustFeed variants exist)
            "Unknown" → "Unknown" (no match)
        """
        from rapidfuzz import fuzz, process

        # Only apply fuzzy matching for power_source, feeder, cooler
        if component_type not in ["power_source", "feeder", "cooler"]:
            return user_input

        # Get product names for this component type
        known_products = self.product_names.get(component_type, [])

        if not known_products:
            return user_input

        # Extract first word from user input
        first_word = user_input.split()[0] if user_input else user_input

        # Create normalized version by removing spaces/numbers for matching
        # "Cool2" -> "cool", "COOL 2" -> "cool"
        def normalize_for_matching(text):
            """Remove spaces and numbers to get base word"""
            import re
            # Extract alphabetic characters only from first word
            first_word_part = text.split()[0] if text else text
            return re.sub(r'[^a-zA-Z]', '', first_word_part).lower()

        normalized_input = normalize_for_matching(user_input)

        # Count how many products share the same base name (ignoring spaces/numbers)
        products_with_same_base = [
            p for p in known_products
            if normalize_for_matching(p) == normalized_input or p.lower().startswith(first_word.lower())
        ]

        # If multiple products share the same base name, return the normalized base
        # This ensures we match both "Cool2" and "COOL 2" when searching
        if len(products_with_same_base) > 1:
            logger.info(f"Found {len(products_with_same_base)} products matching base name '{normalized_input}' in {component_type}")
            # Return the first product's first word (which exists in Neo4j) rather than user's input
            # This ensures search will match the actual product names in the database
            first_product_first_word = products_with_same_base[0].split()[0]
            logger.info(f"Returning first word from actual product '{first_product_first_word}' to enable multi-product search")
            return first_product_first_word

        # Otherwise, try fuzzy matching
        matches = process.extract(
            user_input,
            known_products,
            scorer=fuzz.ratio,
            score_cutoff=80,
            limit=1  # Get best match only
        )

        if not matches:
            logger.info(f"No fuzzy match found for '{user_input}' in {component_type}")
            return user_input

        # Single match - return exact product name
        matched_name, score, _ = matches[0]
        logger.info(f"Fuzzy matched '{user_input}' to '{matched_name}' (score: {score})")
        return matched_name

    def _expand_measurement_terms(self, value: str) -> List[str]:
        """
        Expand measurement terms to include decimal variants with word boundaries

        Logic:
        - Detect length measurements without decimals: "5m", "2mm", "10cm"
        - Generate decimal variant with spaces: "5m" → [" 5m", " 5.0m"]
        - Preserve electrical specs: "500 A" → [" 500 A"]
        - Already has decimal: "5.0m" → [" 5.0m"]
        - Add leading space for word boundary matching in CONTAINS queries

        Args:
            value: Search term that may contain measurements

        Returns:
            List of search term variations with word boundaries (original + decimal variant if applicable)
        """
        import re

        # Pattern: number (without decimal) followed by length unit
        # Matches: "5m", "2mm", "10cm", "3km"
        # Does NOT match: "5.0m", "500 A", "230V"
        length_pattern = r'\b(\d+)\s*(m|mm|cm|km)\b'

        match = re.search(length_pattern, value, flags=re.IGNORECASE)

        if match and '.' not in match.group(1):
            # Found length measurement without decimal
            number = match.group(1)
            unit = match.group(2)

            # Generate variants with leading space for word boundary matching
            # This prevents "5.0m" from matching "15.0m"
            original_with_space = f" {value}"
            decimal_variant = f" {number}.0{unit}"

            logger.info(f"Expanded measurement term: '{value}' → ['{original_with_space}', '{decimal_variant}']")
            return [original_with_space, decimal_variant]

        # No length measurement pattern or already has decimal
        # Still add leading space for word boundary
        term_with_space = f" {value}"
        logger.info(f"Added word boundary to term: '{value}' → '{term_with_space}'")
        return [term_with_space]

    def _build_search_terms_from_component(
        self,
        component_dict: Dict[str, Optional[str]],
        component_type: str
    ) -> List[str]:
        """
        Generic search term builder from component dict with fuzzy product name normalization
        Loops through component features and builds search terms for CONTAINS query

        Now includes measurement term expansion for better format matching:
        - "5m" generates both "5m" and "5.0m" search terms
        - "500 A" remains as-is (electrical specs not expanded)

        Args:
            component_dict: Component-specific requirements dict (e.g., power_source dict)
            component_type: Component category (power_source, feeder, cooler, etc.)

        Returns:
            List of search terms extracted from component features (may include variants)
        """
        search_terms = []

        if not component_dict or not isinstance(component_dict, dict):
            return search_terms

        # Loop through all features in component dict
        for key, value in component_dict.items():
            if value and isinstance(value, str) and value.strip():
                # Apply fuzzy normalization for product_name field only
                if key == "product_name" and component_type in ["power_source", "feeder", "cooler"]:
                    normalized_value = self._normalize_product_name(value.strip(), component_type)
                    search_terms.append(normalized_value)
                else:
                    # Expand measurement terms to include decimal variants
                    expanded_terms = self._expand_measurement_terms(value.strip())
                    search_terms.extend(expanded_terms)

        logger.info(f"Built {len(search_terms)} search terms from component: {search_terms}")
        return search_terms

    def _add_search_term_filters(
        self,
        query: str,
        params: Dict[str, Any],
        search_terms: List[str],
        node_alias: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generic search term filter builder - adds CONTAINS conditions to query

        Reusable across all product categories to eliminate code duplication

        Args:
            query: Base Cypher query string
            params: Query parameters dict
            search_terms: List of search terms to filter by
            node_alias: Node variable name in query (p, f, c, i, t, a)

        Returns:
            Tuple of (updated_query, updated_params)

        Example:
            query, params = self._add_search_term_filters(
                query, params, ["water-cooled", "5.0m"], "t"
            )
            # Adds: AND ((toLower(t.description) CONTAINS ...) OR (...))
        """
        if not search_terms:
            return query, params

        conditions = []
        for idx, term in enumerate(search_terms):
            param_name = f"term_{idx}"
            conditions.append(
                f"(toLower({node_alias}.description) CONTAINS toLower(${param_name}) "
                f"OR toLower({node_alias}.embedding_text) CONTAINS toLower(${param_name}) "
                f"OR toLower({node_alias}.name) CONTAINS toLower(${param_name}))"
            )
            params[param_name] = term

        query += " AND (" + " OR ".join(conditions) + ")"
        return query, params

    async def _execute_search_with_fallback(
        self,
        primary_query: str,
        primary_params: Dict[str, Any],
        fallback_query: str,
        fallback_params: Dict[str, Any],
        search_terms: List[str],
        filters_applied: Dict[str, Any],
        category: str
    ) -> Tuple[List[ProductResult], Dict[str, Any]]:
        """
        Execute search with fallback logic - tries specific search first, falls back to broader search

        Universal fallback handler for all product categories

        Args:
            primary_query: Query with search term filters
            primary_params: Parameters for primary query
            fallback_query: Query without search term filters (broader)
            fallback_params: Parameters for fallback query
            search_terms: Original search terms (for user message)
            filters_applied: Filters metadata dict
            category: Product category name (for logging)

        Returns:
            Tuple of (products, updated_filters_applied)

        Logic:
            1. Try primary search with search terms
            2. If no results AND search terms were provided → fallback to broader search
            3. Update filters_applied with fallback message if used
        """
        # Try primary search
        products = await self._execute_search(primary_query, primary_params)

        # Fallback: If search terms provided but no results, show all compatible products
        if search_terms and len(products) == 0:
            logger.info(
                f"No {category} found matching search terms {search_terms}, "
                f"falling back to all compatible {category}"
            )

            products = await self._execute_search(fallback_query, fallback_params)

            if products:
                logger.info(f"Fallback found {len(products)} compatible {category}")
                filters_applied["fallback_used"] = True
                filters_applied["original_search_terms"] = search_terms
                filters_applied["message"] = (
                    f"No {category} found matching '{', '.join(search_terms)}'. "
                    f"Showing all compatible {category}."
                )

        return products, filters_applied

    async def search_power_source(
        self,
        master_parameters: Dict[str, Any],
        limit: int = 10
    ) -> SearchResults:
        """
        S1: Search for power sources based on requirements
        PowerSource is MANDATORY - always return results
        Uses modular helpers for search term filtering and fallback logic
        """

        # Build base query
        base_query = """
        MATCH (p:Product)
        WHERE p.category = 'PowerSource'
        AND p.is_available = true
        """
        params = {}
        filters_applied = {}

        # Extract power_source component dict and build search terms
        power_source_dict = master_parameters.get("power_source", {})
        search_terms = self._build_search_terms_from_component(power_source_dict, "power_source")

        # Build primary query with search term filters (if any)
        primary_query = base_query
        primary_params = params.copy()

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "power_source"
            primary_query, primary_params = self._add_search_term_filters(
                primary_query, primary_params, search_terms, "p"
            )

        # Add RETURN clause (with DISTINCT to prevent duplicates)
        return_clause = """
        RETURN DISTINCT p.gin as gin, p.name as name, p.category as category,
               p.description as description,
               p.specifications_json as specifications_json,
               p.embedding_text as embedding_text,
               p as specifications
        ORDER BY p.name
        LIMIT $limit
        """
        primary_query += return_clause
        primary_params["limit"] = limit

        # Build fallback query (without search term filters)
        fallback_query = base_query + return_clause
        fallback_params = params.copy()
        fallback_params["limit"] = limit

        # Execute with fallback logic
        products, filters_applied = await self._execute_search_with_fallback(
            primary_query=primary_query,
            primary_params=primary_params,
            fallback_query=fallback_query,
            fallback_params=fallback_params,
            search_terms=search_terms,
            filters_applied=filters_applied,
            category="PowerSource"
        )

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied=filters_applied,
            compatibility_validated=False  # S1 doesn't need compatibility
        )

    async def search_feeder(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        limit: int = 10
    ) -> SearchResults:
        """
        S2: Search for feeders determined by selected PowerSource
        Uses DETERMINES relationship (not COMPATIBLE_WITH)
        Uses modular helpers for search term filtering and fallback logic
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search feeders")
            return SearchResults(products=[], total_count=0, filters_applied={})

        # Build base compatibility query
        base_query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:DETERMINES]-(f:Product)
        WHERE f.category = 'Feeder'
        AND f.is_available = true
        """
        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Extract feeder component dict and build search terms
        feeder_dict = master_parameters.get("feeder", {})
        search_terms = self._build_search_terms_from_component(feeder_dict, "feeder")

        # Build primary query with search term filters (if any)
        primary_query = base_query
        primary_params = params.copy()

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "feeder"
            primary_query, primary_params = self._add_search_term_filters(
                primary_query, primary_params, search_terms, "f"
            )

        # Add RETURN clause (with DISTINCT to prevent duplicates)
        return_clause = """
        RETURN DISTINCT f.gin as gin, f.name as name, f.category as category,
               f.description as description,
               f.specifications_json as specifications_json,
               f as specifications
        ORDER BY f.name
        LIMIT $limit
        """
        primary_query += return_clause
        primary_params["limit"] = limit

        # Build fallback query (without search term filters)
        fallback_query = base_query + return_clause
        fallback_params = params.copy()
        fallback_params["limit"] = limit

        # Execute with fallback logic
        products, filters_applied = await self._execute_search_with_fallback(
            primary_query=primary_query,
            primary_params=primary_params,
            fallback_query=fallback_query,
            fallback_params=fallback_params,
            search_terms=search_terms,
            filters_applied=filters_applied,
            category="Feeder"
        )

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied=filters_applied,
            compatibility_validated=True
        )

    async def search_cooler(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        limit: int = 10
    ) -> SearchResults:
        """
        S3: Search for coolers determined by PowerSource
        Uses DETERMINES relationship (not COMPATIBLE_WITH)
        Uses modular helpers for search term filtering and fallback logic
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search coolers")
            return SearchResults(products=[], total_count=0, filters_applied={})

        # Build base compatibility query
        base_query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:DETERMINES]-(c:Product)
        WHERE c.category = 'Cooler'
        AND c.is_available = true
        """
        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Extract cooler component dict and build search terms
        cooler_dict = master_parameters.get("cooler", {})
        search_terms = self._build_search_terms_from_component(cooler_dict, "cooler")

        # Build primary query with search term filters (if any)
        primary_query = base_query
        primary_params = params.copy()

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "cooler"
            primary_query, primary_params = self._add_search_term_filters(
                primary_query, primary_params, search_terms, "c"
            )

        # Add RETURN clause (with DISTINCT to prevent duplicates)
        return_clause = """
        RETURN DISTINCT c.gin as gin, c.name as name, c.category as category,
               c.description as description,
               c.specifications_json as specifications_json,
               c as specifications
        ORDER BY c.name
        LIMIT $limit
        """
        primary_query += return_clause
        primary_params["limit"] = limit

        # Build fallback query (without search term filters)
        fallback_query = base_query + return_clause
        fallback_params = params.copy()
        fallback_params["limit"] = limit

        # Execute with fallback logic
        products, filters_applied = await self._execute_search_with_fallback(
            primary_query=primary_query,
            primary_params=primary_params,
            fallback_query=fallback_query,
            fallback_params=fallback_params,
            search_terms=search_terms,
            filters_applied=filters_applied,
            category="Cooler"
        )

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied=filters_applied,
            compatibility_validated=True
        )

    async def search_interconnector(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        limit: int = 10
    ) -> SearchResults:
        """
        S4: Search for interconnectors compatible with PowerSource
        Uses COMPATIBLE_WITH relationship (interconnectors only compatible with PowerSource)
        Uses modular helpers for search term filtering and fallback logic
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search interconnectors")
            return SearchResults(products=[], total_count=0, filters_applied={})

        # Build base compatibility query
        base_query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(i:Product)
        WHERE i.category = 'Interconnector'
        AND i.is_available = true
        """
        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Extract interconnector component dict and build search terms
        interconnector_dict = master_parameters.get("interconnector", {})
        search_terms = self._build_search_terms_from_component(interconnector_dict, "interconnector")

        # Build primary query with search term filters (if any)
        primary_query = base_query
        primary_params = params.copy()

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "interconnector"
            primary_query, primary_params = self._add_search_term_filters(
                primary_query, primary_params, search_terms, "i"
            )

        # Add RETURN clause (with DISTINCT to prevent duplicates)
        return_clause = """
        RETURN DISTINCT i.gin as gin, i.name as name, i.category as category,
               i.description as description,
               i.specifications_json as specifications_json,
               i as specifications
        ORDER BY i.name
        LIMIT $limit
        """
        primary_query += return_clause
        primary_params["limit"] = limit

        # Build fallback query (without search term filters)
        fallback_query = base_query + return_clause
        fallback_params = params.copy()
        fallback_params["limit"] = limit

        # Execute with fallback logic
        products, filters_applied = await self._execute_search_with_fallback(
            primary_query=primary_query,
            primary_params=primary_params,
            fallback_query=fallback_query,
            fallback_params=fallback_params,
            search_terms=search_terms,
            filters_applied=filters_applied,
            category="Interconnector"
        )

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied=filters_applied,
            compatibility_validated=True
        )

    async def search_torch(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        limit: int = 10
    ) -> SearchResults:
        """
        S5: Search for torches compatible with PowerSource
        Uses modular helpers for search term filtering and fallback logic

        NOTE: Torches are only filtered by PowerSource compatibility.
        Cooler selection does NOT filter torches because:
        - Coolers are for feeder cooling, not torch cooling
        - Torches have independent cooling mechanisms (gas-cooled or water-cooled)
        - Gas-cooled torches have no cooler compatibility relationships (self-cooled)
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search torches")
            return SearchResults(products=[], total_count=0, filters_applied={})

        # Build base compatibility query - torches only need PowerSource compatibility
        base_query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(t:Product)
        WHERE t.category = 'Torch'
        AND t.is_available = true
        """
        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Extract torch component dict and build search terms
        torch_dict = master_parameters.get("torch", {})
        search_terms = self._build_search_terms_from_component(torch_dict, "torch")

        # Build primary query with search term filters (if any)
        primary_query = base_query
        primary_params = params.copy()

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "torch"
            primary_query, primary_params = self._add_search_term_filters(
                primary_query, primary_params, search_terms, "t"
            )

        # Add RETURN clause (with DISTINCT to prevent duplicates)
        return_clause = """
        RETURN DISTINCT t.gin as gin, t.name as name, t.category as category,
               t.description as description,
               t.specifications_json as specifications_json,
               t as specifications
        ORDER BY t.name
        LIMIT $limit
        """
        primary_query += return_clause
        primary_params["limit"] = limit

        # Build fallback query (without search term filters)
        fallback_query = base_query + return_clause
        fallback_params = params.copy()
        fallback_params["limit"] = limit

        # Execute with fallback logic
        products, filters_applied = await self._execute_search_with_fallback(
            primary_query=primary_query,
            primary_params=primary_params,
            fallback_query=fallback_query,
            fallback_params=fallback_params,
            search_terms=search_terms,
            filters_applied=filters_applied,
            category="Torch"
        )

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied=filters_applied,
            compatibility_validated=True
        )

    async def search_accessories(
        self,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        accessory_category: str = None,  # Now optional, defaults to all accessories
        limit: int = 10
    ) -> SearchResults:
        """
        S6: Search for accessories across all accessory categories
        Searches: PowerSourceAccessory, FeederAccessory, ConnectivityAccessory, Accessory
        Uses modular helpers for search term filtering and fallback logic

        Note: Searches all categories containing 'Accessory' using CONTAINS clause
        This allows finding trolleys (PowerSourceAccessory) without knowing exact category
        """

        # Build compatibility filter based on what's been selected
        compatibility_filters = []
        params = {}
        filters_applied = {"search_mode": "all_accessories"}

        # Check which components have been selected
        power_source_gin = response_json.get("PowerSource", {}).get("gin")
        feeder_gin = response_json.get("Feeder", {}).get("gin")
        cooler_gin = response_json.get("Cooler", {}).get("gin")

        # Get already-selected accessory GINs to exclude them
        selected_accessories = response_json.get("Accessories", [])
        selected_gins = [acc.get("gin") for acc in selected_accessories if isinstance(acc, dict)]

        if selected_gins:
            params["excluded_gins"] = selected_gins
            filters_applied["excluded_accessories"] = selected_gins

        # Build base query to search across ALL accessory categories
        # We'll use UNION to combine results from different compatibility paths
        if power_source_gin or feeder_gin or cooler_gin:
            # Build UNION query for multiple compatibility paths
            union_parts = []

            # Build exclusion clause
            exclusion_clause = ""
            if selected_gins:
                exclusion_clause = " AND NOT a.gin IN $excluded_gins"

            if power_source_gin:
                compatibility_filters.append("ps")
                params["power_source_gin"] = power_source_gin
                filters_applied["compatible_with_power_source"] = power_source_gin
                union_parts.append(f"""
                    MATCH (ps:Product {{gin: $power_source_gin}})-[:COMPATIBLE_WITH]-(a:Product)
                    WHERE a.category CONTAINS 'Accessory' AND a.is_available = true{exclusion_clause}
                """)

            if feeder_gin:
                compatibility_filters.append("f")
                params["feeder_gin"] = feeder_gin
                filters_applied["compatible_with_feeder"] = feeder_gin
                union_parts.append(f"""
                    MATCH (f:Product {{gin: $feeder_gin}})-[:COMPATIBLE_WITH]-(a:Product)
                    WHERE a.category CONTAINS 'Accessory' AND a.is_available = true{exclusion_clause}
                """)

            if cooler_gin:
                compatibility_filters.append("c")
                params["cooler_gin"] = cooler_gin
                filters_applied["compatible_with_cooler"] = cooler_gin
                union_parts.append(f"""
                    MATCH (c:Product {{gin: $cooler_gin}})-[:COMPATIBLE_WITH]-(a:Product)
                    WHERE a.category CONTAINS 'Accessory' AND a.is_available = true{exclusion_clause}
                """)

            # Combine with UNION to get all compatible accessories
            base_query = "\nUNION\n".join(union_parts)
        else:
            # No components selected yet - just filter by all accessory categories
            exclusion_clause = ""
            if selected_gins:
                exclusion_clause = " AND NOT a.gin IN $excluded_gins"
            base_query = f"MATCH (a:Product) WHERE a.category CONTAINS 'Accessory' AND a.is_available = true{exclusion_clause}"

        # Extract accessories component dict and build search terms
        accessories_dict = master_parameters.get("accessories", {})
        search_terms = self._build_search_terms_from_component(accessories_dict, "accessories")

        # Build primary query with search term filters (if any)
        primary_query = base_query
        primary_params = params.copy()

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "accessories"
            primary_query, primary_params = self._add_search_term_filters(
                primary_query, primary_params, search_terms, "a"
            )

        # Add RETURN clause (with DISTINCT to prevent duplicates)
        return_clause = """
        RETURN DISTINCT a.gin as gin, a.name as name, a.category as category,
               a.description as description,
               a.specifications_json as specifications_json,
               a as specifications
        ORDER BY a.name
        LIMIT $limit
        """
        primary_query += return_clause
        primary_params["limit"] = limit

        # Build fallback query (without search term filters)
        fallback_query = base_query + return_clause
        fallback_params = params.copy()
        fallback_params["limit"] = limit

        # Execute with fallback logic
        products, filters_applied = await self._execute_search_with_fallback(
            primary_query=primary_query,
            primary_params=primary_params,
            fallback_query=fallback_query,
            fallback_params=fallback_params,
            search_terms=search_terms,
            filters_applied=filters_applied,
            category="Accessory"
        )

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied=filters_applied,
            compatibility_validated=bool(compatibility_filters)
        )

    async def _execute_search(self, query: str, params: Dict[str, Any]) -> List[ProductResult]:
        """Execute Neo4j search query and return results"""

        try:
            async with self.driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()

                products = []
                for record in records:
                    # Extract specifications from node properties
                    specs = record.get("specifications", {})
                    if hasattr(specs, "__dict__"):
                        specs = dict(specs)

                    # Convert Neo4j DateTime objects to ISO strings for JSON serialization
                    specs = self._clean_neo4j_types(specs)

                    product = ProductResult(
                        gin=record["gin"],
                        name=record["name"],
                        category=record["category"],
                        description=record.get("description"),
                        specifications=specs
                    )
                    products.append(product)

                logger.info(f"Search returned {len(products)} products")
                return products

        except Exception as e:
            logger.error(f"Neo4j search failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return []

    def _clean_neo4j_types(self, obj: Any) -> Any:
        """Convert Neo4j-specific types to JSON-serializable types"""
        from neo4j.time import DateTime, Date, Time

        if isinstance(obj, (DateTime, Date, Time)):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._clean_neo4j_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_neo4j_types(item) for item in obj]
        else:
            return obj


# Dependency injection
_neo4j_search = None

async def get_neo4j_search(uri: str, username: str, password: str) -> Neo4jProductSearch:
    """Get singleton Neo4j search instance"""
    global _neo4j_search
    if _neo4j_search is None:
        _neo4j_search = Neo4jProductSearch(uri, username, password)
    return _neo4j_search
