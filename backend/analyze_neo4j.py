"""
Analyze Neo4j Database Structure
Understand the actual schema before finalizing queries
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()


async def analyze_database():
    """Analyze Neo4j database structure"""

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    print("=" * 80)
    print("NEO4J DATABASE ANALYSIS")
    print("=" * 80)

    async with driver.session() as session:

        # 1. Check node labels
        print("\n1. NODE LABELS:")
        print("-" * 80)
        result = await session.run("CALL db.labels()")
        labels = await result.data()
        for record in labels:
            print(f"  - {record['label']}")

        # 2. Check relationship types
        print("\n2. RELATIONSHIP TYPES:")
        print("-" * 80)
        result = await session.run("CALL db.relationshipTypes()")
        rel_types = await result.data()
        for record in rel_types:
            print(f"  - {record['relationshipType']}")

        # 3. Sample Product nodes
        print("\n3. SAMPLE PRODUCT NODES:")
        print("-" * 80)
        result = await session.run("""
            MATCH (p:Product)
            RETURN p
            LIMIT 5
        """)
        products = await result.data()
        for i, record in enumerate(products, 1):
            product = record['p']
            print(f"\n  Product {i}:")
            print(f"    GIN: {product.get('gin')}")
            print(f"    Name: {product.get('name')}")
            print(f"    Category: {product.get('category')}")
            print(f"    Properties: {list(product.keys())}")

        # 4. Check categories
        print("\n4. PRODUCT CATEGORIES:")
        print("-" * 80)
        result = await session.run("""
            MATCH (p:Product)
            RETURN DISTINCT p.category as category, count(*) as count
            ORDER BY category
        """)
        categories = await result.data()
        for record in categories:
            print(f"  - {record['category']}: {record['count']} products")

        # 5. Check PowerSource products specifically
        print("\n5. POWER SOURCE PRODUCTS:")
        print("-" * 80)
        result = await session.run("""
            MATCH (p:Product)
            WHERE p.category = 'PowerSource'
            RETURN p.gin as gin, p.name as name
            LIMIT 10
        """)
        power_sources = await result.data()
        for record in power_sources:
            print(f"  - {record['gin']}: {record['name']}")

        # 6. Check COMPATIBLE_WITH relationships
        print("\n6. COMPATIBLE_WITH RELATIONSHIPS:")
        print("-" * 80)
        result = await session.run("""
            MATCH (p1:Product)-[r:COMPATIBLE_WITH]-(p2:Product)
            RETURN p1.category as cat1, p2.category as cat2, count(*) as count
            ORDER BY count DESC
            LIMIT 20
        """)
        compat = await result.data()
        for record in compat:
            print(f"  - {record['cat1']} ↔ {record['cat2']}: {record['count']} relationships")

        # 7. Sample compatibility for a specific PowerSource
        print("\n7. SAMPLE COMPATIBILITY (Aristo 500ix):")
        print("-" * 80)
        result = await session.run("""
            MATCH (ps:Product {gin: '0446200880'})-[:COMPATIBLE_WITH]-(p:Product)
            RETURN p.category as category, p.name as name
            LIMIT 10
        """)
        aristo_compat = await result.data()
        if aristo_compat:
            for record in aristo_compat:
                print(f"  - {record['category']}: {record['name']}")
        else:
            print("  No compatible products found for Aristo 500ix")

        # 8. Check property structure
        print("\n8. SAMPLE PRODUCT PROPERTIES:")
        print("-" * 80)
        result = await session.run("""
            MATCH (p:Product {gin: '0446200880'})
            RETURN properties(p) as props
        """)
        props_data = await result.data()
        if props_data:
            props = props_data[0]['props']
            print("  Aristo 500ix properties:")
            for key, value in props.items():
                print(f"    {key}: {value}")

    await driver.close()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_database())
