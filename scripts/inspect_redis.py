#!/usr/bin/env python3
"""
Redis Session Inspector - Python Version
Usage: python scripts/inspect_redis.py [session_id]
"""

import sys
import json
import redis
from datetime import datetime, timedelta

def format_session_data(data: dict) -> str:
    """Format session data for readable display"""
    output = []

    # Basic info
    output.append(f"Session ID: {data.get('session_id', 'N/A')}")
    output.append(f"Created: {data.get('created_at', 'N/A')}")
    output.append(f"Language: {data.get('language', 'N/A')}")
    output.append(f"Current State: {data.get('current_state', 'N/A')}")
    output.append("")

    # Master parameters
    output.append("Master Parameters:")
    master_params = data.get('master_parameters', {})
    for key, value in master_params.items():
        if value:
            output.append(f"  • {key}: {value}")
    output.append("")

    # Response JSON (selected products)
    output.append("Selected Products:")
    response_json = data.get('response_json', {})
    for component, product in response_json.items():
        if product and component != 'Accessories':
            output.append(f"  • {component}: {product.get('name', 'N/A')} ({product.get('gin', 'N/A')})")

    accessories = response_json.get('Accessories', [])
    if accessories:
        output.append(f"  • Accessories: {len(accessories)} items")

    output.append("")

    # Conversation history
    conv_history = data.get('conversation_history', [])
    output.append(f"Conversation History ({len(conv_history)} messages):")
    for i, msg in enumerate(conv_history[-5:], 1):  # Show last 5
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')[:100]
        output.append(f"  {i}. [{role}] {content}...")

    return "\n".join(output)

def main():
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    print("=== Redis Session Inspector (Python) ===\n")

    # Get all session keys
    session_keys = r.keys("session:*")
    print(f"📊 Active Sessions: {len(session_keys)}\n")

    if not session_keys:
        print("No active sessions found.")
        print("\nTo create a session, send a POST request to:")
        print("  curl -X POST http://localhost:8000/api/v1/configurator/message \\")
        print("       -H 'Content-Type: application/json' \\")
        print("       -d '{\"message\": \"I need a MIG welder\", \"language\": \"en\"}'")
        return

    # If session_id provided, show that session
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        session_key = f"session:{session_id}"

        if session_key not in session_keys:
            print(f"❌ Session not found: {session_id}")
            print(f"\nAvailable sessions:")
            for key in session_keys:
                print(f"  • {key.replace('session:', '')}")
            return

        # Get session data
        session_json = r.get(session_key)
        session_data = json.loads(session_json)

        # Get TTL
        ttl = r.ttl(session_key)
        ttl_minutes = ttl / 60

        print(f"📄 Session: {session_id}")
        print(f"⏰ TTL: {ttl} seconds ({ttl_minutes:.1f} minutes)\n")
        print("=" * 60)
        print(format_session_data(session_data))
        print("=" * 60)

    else:
        # Show all sessions (summary)
        for key in session_keys:
            session_id = key.replace("session:", "")
            session_json = r.get(key)
            session_data = json.loads(session_json)

            ttl = r.ttl(key)

            print(f"📄 Session: {session_id}")
            print(f"   State: {session_data.get('current_state', 'N/A')}")
            print(f"   Language: {session_data.get('language', 'N/A')}")
            print(f"   Messages: {len(session_data.get('conversation_history', []))}")
            print(f"   TTL: {ttl}s ({ttl/60:.1f}m)")
            print()

    # Redis stats
    print("\n💾 Redis Memory Usage:")
    memory_info = r.info('memory')
    print(f"   Used: {memory_info['used_memory_human']}")
    print(f"   Peak: {memory_info['used_memory_peak_human']}")

    print("\n📦 Redis Database Stats:")
    db_info = r.info('keyspace')
    if db_info:
        print(f"   {db_info}")

if __name__ == "__main__":
    main()
