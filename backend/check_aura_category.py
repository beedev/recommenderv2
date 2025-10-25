"""
Check product categorization in Aura (cloud) Neo4j database
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

async def check_product_category():
    """Check if GIN 0465427880 is correctly categorized in Aura database"""

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    print(f"\n🔍 Checking Aura Database: {uri}")
    print("=" * 80)

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    try:
        async with driver.session() as session:
            # Check the problematic product
            print("\n📦 Checking GIN: 0465427880 (COOL 2 Cooling Unit)")
            result = await session.run("""
                MATCH (n:Product {gin: '0465427880'})
                RETURN n.gin as gin, n.name as name, n.category as category
            """)

            records = await result.data()

            if records:
                for record in records:
                    print(f"  GIN: {record['gin']}")
                    print(f"  Name: {record['name']}")
                    print(f"  Category: {record['category']}")
                    print(f"  Expected Category: Cooler")

                    if record['category'] == 'Cooler':
                        print(f"  ✅ CORRECTLY categorized in Aura database")
                    elif record['category'] == 'PowerSource':
                        print(f"  ❌ MISCATEGORIZED as PowerSource (should be Cooler)")
                    else:
                        print(f"  ⚠️  Unexpected category: {record['category']}")
            else:
                print("  ❌ Product not found in Aura database")

            # Check another problematic product from screenshot
            print("\n📦 Checking GIN: 0700007889 (Counterbalance Arm Extension Kit)")
            result = await session.run("""
                MATCH (n:Product {gin: '0700007889'})
                RETURN n.gin as gin, n.name as name, n.category as category
            """)

            records = await result.data()

            if records:
                for record in records:
                    print(f"  GIN: {record['gin']}")
                    print(f"  Name: {record['name']}")
                    print(f"  Category: {record['category']}")
                    print(f"  Expected Category: Accessory or TorchAccessory")

                    if record['category'] in ['Accessory', 'TorchAccessory', 'PowerSourceAccessory']:
                        print(f"  ✅ CORRECTLY categorized in Aura database")
                    elif record['category'] == 'PowerSource':
                        print(f"  ❌ MISCATEGORIZED as PowerSource (should be Accessory)")
                    else:
                        print(f"  ⚠️  Unexpected category: {record['category']}")
            else:
                print("  ❌ Product not found in Aura database")

            # Check how many PowerSource products exist
            print("\n📊 PowerSource Category Statistics:")
            result = await session.run("""
                MATCH (p:Product {category: 'PowerSource', is_available: true})
                RETURN count(p) as total_power_sources
            """)

            records = await result.data()
            if records:
                print(f"  Total PowerSource products: {records[0]['total_power_sources']}")

            # Sample a few PowerSource products to see if they're correctly categorized
            print("\n📋 Sample of PowerSource products:")
            result = await session.run("""
                MATCH (p:Product {category: 'PowerSource', is_available: true})
                RETURN p.gin as gin, p.name as name
                ORDER BY p.name
                LIMIT 5
            """)

            records = await result.data()
            for record in records:
                print(f"  - {record['name']} (GIN: {record['gin']})")

    finally:
        await driver.close()

    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(check_product_category())
