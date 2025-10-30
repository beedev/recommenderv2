#!/bin/bash
# Redis Session Inspector
# Usage: ./scripts/inspect_redis.sh [session_id]

echo "=== Redis Session Inspector ==="
echo ""

# Count active sessions
SESSION_COUNT=$(redis-cli KEYS "session:*" | wc -l)
echo "📊 Active Sessions: $SESSION_COUNT"
echo ""

# List all session keys
echo "🔑 Session Keys:"
redis-cli KEYS "session:*"
echo ""

# If session_id provided, show that session
if [ ! -z "$1" ]; then
    echo "📄 Session Data for: $1"
    echo "---"
    redis-cli GET "session:$1" | python3 -m json.tool
    echo ""

    # Show TTL
    TTL=$(redis-cli TTL "session:$1")
    echo "⏰ TTL: $TTL seconds ($(echo "scale=2; $TTL/60" | bc) minutes)"
else
    # Show all sessions
    for key in $(redis-cli KEYS "session:*"); do
        SESSION_ID=$(echo $key | sed 's/session://')
        echo "📄 Session: $SESSION_ID"
        TTL=$(redis-cli TTL "$key")
        echo "   TTL: $TTL seconds"
        echo "   Data:"
        redis-cli GET "$key" | python3 -m json.tool | head -20
        echo "   ..."
        echo ""
    done
fi

# Show Redis memory usage
echo "💾 Redis Memory Usage:"
redis-cli INFO memory | grep used_memory_human
echo ""

# Show Redis database size
echo "📦 Redis Database Stats:"
redis-cli INFO keyspace
