"""
Simplified Neo4j Product Search Service for S1→S7 Flow
Handles component-specific searches with compatibility validation
"""

import logging
from typing import Dict, List, Optional, Any
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
        logger.info(f"Neo4j Product Search initialized - URI: {uri}")

    async def close(self):
        """Close Neo4j connection"""
        await self.driver.close()

    def _build_search_terms_from_component(self, component_dict: Dict[str, Optional[str]]) -> List[str]:
        """
        Generic search term builder from component dict
        Loops through component features and builds search terms for CONTAINS query

        Args:
            component_dict: Component-specific requirements dict (e.g., power_source dict)

        Returns:
            List of search terms extracted from component features
        """
        search_terms = []

        if not component_dict or not isinstance(component_dict, dict):
            return search_terms

        # Loop through all features in component dict
        for key, value in component_dict.items():
            if value and isinstance(value, str) and value.strip():
                # Add the feature value as a search term
                search_terms.append(value.strip())

        logger.info(f"Built {len(search_terms)} search terms from component: {search_terms}")
        return search_terms

    async def search_power_source(
        self,
        master_parameters: Dict[str, Any],
        limit: int = 10
    ) -> SearchResults:
        """
        S1: Search for power sources based on requirements
        PowerSource is MANDATORY - always return results
        Uses power_source component dict to build search terms
        """

        query = """
        MATCH (p:Product)
        WHERE p.category = 'PowerSource'
        AND p.is_available = true
        """

        params = {}
        filters_applied = {}

        # Extract power_source component dict and build search terms
        power_source_dict = master_parameters.get("power_source", {})
        search_terms = self._build_search_terms_from_component(power_source_dict)

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "power_source"

            # Apply text-based search on description using CONTAINS
            conditions = []
            for idx, term in enumerate(search_terms):
                param_name = f"term_{idx}"
                conditions.append(f"(p.description CONTAINS ${param_name} OR p.embedding_text CONTAINS ${param_name})")
                params[param_name] = term

            query += " AND (" + " OR ".join(conditions) + ")"

        # Return results with description, specifications_json
        query += """
        RETURN p.gin as gin, p.name as name, p.category as category,
               p.description as description,
               p.specifications_json as specifications_json,
               p.embedding_text as embedding_text,
               p as specifications
        ORDER BY p.name
        LIMIT $limit
        """
        params["limit"] = limit

        # Execute query
        products = await self._execute_search(query, params)

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
        Uses feeder component dict to build search terms
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search feeders")
            return SearchResults(products=[], total_count=0, filters_applied={})

        query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:DETERMINES]-(f:Product)
        WHERE f.category = 'Feeder'
        AND f.is_available = true
        """

        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Extract feeder component dict and build search terms
        feeder_dict = master_parameters.get("feeder", {})
        search_terms = self._build_search_terms_from_component(feeder_dict)

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "feeder"

            # Apply text-based search on description using CONTAINS
            conditions = []
            for idx, term in enumerate(search_terms):
                param_name = f"term_{idx}"
                conditions.append(f"(f.description CONTAINS ${param_name} OR f.embedding_text CONTAINS ${param_name})")
                params[param_name] = term

            query += " AND (" + " OR ".join(conditions) + ")"

        query += """
        RETURN DISTINCT f.gin as gin, f.name as name, f.category as category,
               f.description as description,
               f.specifications_json as specifications_json,
               f as specifications
        ORDER BY f.name
        LIMIT $limit
        """
        params["limit"] = limit

        products = await self._execute_search(query, params)

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
        Uses cooler component dict to build search terms
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")
        feeder_gin = response_json.get("Feeder", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search coolers")
            return SearchResults(products=[], total_count=0, filters_applied={})

        query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:DETERMINES]-(c:Product)
        WHERE c.category = 'Cooler'
        AND c.is_available = true
        """

        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Add feeder compatibility if feeder was selected
        if feeder_gin:
            query += """
            AND ($feeder_gin IS NULL OR EXISTS((c)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))
            """
            params["feeder_gin"] = feeder_gin
            filters_applied["compatible_with_feeder"] = feeder_gin
        else:
            params["feeder_gin"] = None

        # Extract cooler component dict and build search terms
        cooler_dict = master_parameters.get("cooler", {})
        search_terms = self._build_search_terms_from_component(cooler_dict)

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "cooler"

            # Apply text-based search on description using CONTAINS
            conditions = []
            for idx, term in enumerate(search_terms):
                param_name = f"term_{idx}"
                conditions.append(f"(c.description CONTAINS ${param_name} OR c.embedding_text CONTAINS ${param_name})")
                params[param_name] = term

            query += " AND (" + " OR ".join(conditions) + ")"

        query += """
        RETURN DISTINCT c.gin as gin, c.name as name, c.category as category,
               c.description as description,
               c.specifications_json as specifications_json,
               c as specifications
        ORDER BY c.name
        LIMIT $limit
        """
        params["limit"] = limit

        products = await self._execute_search(query, params)

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
        S4: Search for interconnectors compatible with PowerSource, Feeder, and Cooler
        Uses interconnector component dict to build search terms
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")
        feeder_gin = response_json.get("Feeder", {}).get("gin")
        cooler_gin = response_json.get("Cooler", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search interconnectors")
            return SearchResults(products=[], total_count=0, filters_applied={})

        query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(i:Product)
        WHERE i.category = 'Interconnector'
        AND i.is_available = true
        """

        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Add feeder compatibility if selected
        if feeder_gin:
            query += """
            AND ($feeder_gin IS NULL OR EXISTS((i)-[:COMPATIBLE_WITH]-(:Product {gin: $feeder_gin})))
            """
            params["feeder_gin"] = feeder_gin
            filters_applied["compatible_with_feeder"] = feeder_gin
        else:
            params["feeder_gin"] = None

        # Add cooler compatibility if selected
        if cooler_gin:
            query += """
            AND ($cooler_gin IS NULL OR EXISTS((i)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin})))
            """
            params["cooler_gin"] = cooler_gin
            filters_applied["compatible_with_cooler"] = cooler_gin
        else:
            params["cooler_gin"] = None

        # Extract interconnector component dict and build search terms
        interconnector_dict = master_parameters.get("interconnector", {})
        search_terms = self._build_search_terms_from_component(interconnector_dict)

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "interconnector"

            # Apply text-based search on description using CONTAINS
            conditions = []
            for idx, term in enumerate(search_terms):
                param_name = f"term_{idx}"
                conditions.append(f"(i.description CONTAINS ${param_name} OR i.embedding_text CONTAINS ${param_name})")
                params[param_name] = term

            query += " AND (" + " OR ".join(conditions) + ")"

        query += """
        RETURN i.gin as gin, i.name as name, i.category as category,
               i.description as description,
               i.specifications_json as specifications_json,
               i as specifications
        ORDER BY i.name
        LIMIT $limit
        """
        params["limit"] = limit

        products = await self._execute_search(query, params)

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
        S5: Search for torches compatible with PowerSource (based on DB analysis)
        Uses torch component dict to build search terms
        NOTE: DB analysis shows PowerSource ↔ Torch relationships exist (336 relationships)
        """

        power_source_gin = response_json.get("PowerSource", {}).get("gin")
        feeder_gin = response_json.get("Feeder", {}).get("gin")
        cooler_gin = response_json.get("Cooler", {}).get("gin")

        if not power_source_gin:
            logger.warning("No PowerSource selected - cannot search torches")
            return SearchResults(products=[], total_count=0, filters_applied={})

        # Use PowerSource as base (DB analysis confirmed this relationship exists)
        query = """
        MATCH (ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(t:Product)
        WHERE t.category = 'Torch'
        AND t.is_available = true
        """
        params = {"power_source_gin": power_source_gin}
        filters_applied = {"compatible_with_power_source": power_source_gin}

        # Add cooler compatibility if selected
        if cooler_gin:
            query += """
            AND ($cooler_gin IS NULL OR EXISTS((t)-[:COMPATIBLE_WITH]-(:Product {gin: $cooler_gin})))
            """
            params["cooler_gin"] = cooler_gin
            filters_applied["compatible_with_cooler"] = cooler_gin
        else:
            params["cooler_gin"] = None

        # Extract torch component dict and build search terms
        torch_dict = master_parameters.get("torch", {})
        search_terms = self._build_search_terms_from_component(torch_dict)

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "torch"

            # Apply text-based search on description using CONTAINS
            conditions = []
            for idx, term in enumerate(search_terms):
                param_name = f"term_{idx}"
                conditions.append(f"(t.description CONTAINS ${param_name} OR t.embedding_text CONTAINS ${param_name})")
                params[param_name] = term

            query += " AND (" + " OR ".join(conditions) + ")"

        query += """
        RETURN t.gin as gin, t.name as name, t.category as category,
               t.description as description,
               t.specifications_json as specifications_json,
               t as specifications
        ORDER BY t.name
        LIMIT $limit
        """
        params["limit"] = limit

        products = await self._execute_search(query, params)

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
        accessory_category: str,
        limit: int = 10
    ) -> SearchResults:
        """
        S6: Search for accessories based on category
        Categories: PowerSourceAccessory, FeederAccessory, ConnectivityAccessory, Remote, Accessory
        Uses accessories component dict to build search terms
        """

        # Build compatibility filter based on what's been selected
        compatibility_filters = []
        params = {"category": accessory_category, "limit": limit}
        filters_applied = {"accessory_category": accessory_category}

        # Check which components have been selected
        if response_json.get("PowerSource", {}).get("gin"):
            compatibility_filters.append("ps")
            params["power_source_gin"] = response_json["PowerSource"]["gin"]
            filters_applied["compatible_with_power_source"] = params["power_source_gin"]

        if response_json.get("Feeder", {}).get("gin"):
            compatibility_filters.append("f")
            params["feeder_gin"] = response_json["Feeder"]["gin"]
            filters_applied["compatible_with_feeder"] = params["feeder_gin"]

        # Build query based on available components
        if compatibility_filters:
            query = "MATCH "
            match_parts = []

            if "ps" in compatibility_filters:
                match_parts.append("(ps:Product {gin: $power_source_gin})-[:COMPATIBLE_WITH]-(a:Product)")
            if "f" in compatibility_filters and "ps" not in compatibility_filters:
                match_parts.append("(f:Product {gin: $feeder_gin})-[:COMPATIBLE_WITH]-(a:Product)")

            query += match_parts[0]
            query += " WHERE a.category = $category AND a.is_available = true"
        else:
            # No components selected yet - just filter by category
            query = "MATCH (a:Product) WHERE a.category = $category AND a.is_available = true"

        # Extract accessories component dict and build search terms
        accessories_dict = master_parameters.get("accessories", {})
        search_terms = self._build_search_terms_from_component(accessories_dict)

        if search_terms:
            filters_applied["search_terms"] = search_terms
            filters_applied["component"] = "accessories"

            # Apply text-based search on description using CONTAINS
            conditions = []
            for idx, term in enumerate(search_terms):
                param_name = f"term_{idx}"
                conditions.append(f"(a.description CONTAINS ${param_name} OR a.embedding_text CONTAINS ${param_name})")
                params[param_name] = term

            query += " AND (" + " OR ".join(conditions) + ")"

        query += """
        RETURN a.gin as gin, a.name as name, a.category as category,
               a.description as description,
               a.specifications_json as specifications_json,
               a as specifications
        ORDER BY a.name
        LIMIT $limit
        """

        products = await self._execute_search(query, params)

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
