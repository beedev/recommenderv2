"""
Script to extract product names from Neo4j by category
Run this to populate app/config/product_names.json
"""

import asyncio
import json
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()


async def extract_product_names():
    """Extract product names from Neo4j grouped by category"""

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    categories = ['PowerSource', 'Feeder', 'Cooler', 'Interconnector', 'Torch', 'Accessory']
    product_names = {}

    try:
        async with driver.session() as session:
            for category in categories:
                query = """
                MATCH (p:Product {category: $category})
                WHERE p.is_available = true
                RETURN p.name, p.gin
                ORDER BY p.name
                LIMIT 100
                """

                result = await session.run(query, {"category": category})
                records = await result.data()

                # Store product names
                key = category.lower().replace('source', '_source')
                product_names[key] = [record["p.name"] for record in records if record["p.name"]]

                print(f"\n{category}: Found {len(product_names[key])} products")
                print(f"Sample: {product_names[key][:5]}")

        # Save to config file
        config_dir = "app/config"
        os.makedirs(config_dir, exist_ok=True)

        with open(f"{config_dir}/product_names.json", "w") as f:
            json.dump(product_names, f, indent=2)

        print(f"\n✅ Product names saved to {config_dir}/product_names.json")
        print(f"\nTotal categories: {len(product_names)}")
        for cat, names in product_names.items():
            print(f"  {cat}: {len(names)} products")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(extract_product_names())
