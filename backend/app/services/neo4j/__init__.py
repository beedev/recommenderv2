"""Neo4j service package - Product search with compatibility validation"""

from .product_search import (
    Neo4jProductSearch,
    ProductResult,
    SearchResults,
    get_neo4j_search
)

__all__ = [
    "Neo4jProductSearch",
    "ProductResult",
    "SearchResults",
    "get_neo4j_search"
]
