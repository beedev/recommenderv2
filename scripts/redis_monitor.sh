#!/bin/bash
# Redis Monitor Control Script
# Usage: ./scripts/redis_monitor.sh [start|stop|restart|status]

PORT=8002
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.redis_monitor.pid"
LOG_FILE="$SCRIPT_DIR/redis_monitor.log"

start_monitor() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "❌ Redis monitor already running (PID: $PID)"
            echo "   Dashboard: http://localhost:$PORT"
            return 1
        else
            rm -f "$PID_FILE"
        fi
    fi

    echo "🚀 Starting Redis Monitor Server..."

    # Start the server in background
    nohup python3 "$SCRIPT_DIR/redis_monitor_server.py" > "$LOG_FILE" 2>&1 &
    PID=$!

    # Save PID
    echo $PID > "$PID_FILE"

    # Wait a moment and check if it started
    sleep 2

    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Redis monitor started successfully!"
        echo ""
        echo "📊 Dashboard: http://localhost:$PORT"
        echo "🔌 API: http://localhost:$PORT/api/redis-data"
        echo "📝 Logs: $LOG_FILE"
        echo "🆔 PID: $PID"
        echo ""
        echo "💡 Use './scripts/redis_monitor.sh stop' to stop"
    else
        echo "❌ Failed to start Redis monitor"
        echo "Check logs: cat $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_monitor() {
    if [ ! -f "$PID_FILE" ]; then
        echo "❌ Redis monitor is not running (no PID file found)"

        # Check if process is running on port anyway
        PID=$(lsof -ti:$PORT)
        if [ ! -z "$PID" ]; then
            echo "⚠️  Found process on port $PORT (PID: $PID)"
            read -p "Kill this process? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                kill $PID
                echo "✅ Process killed"
            fi
        fi
        return 1
    fi

    PID=$(cat "$PID_FILE")

    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 Stopping Redis monitor (PID: $PID)..."
        kill $PID

        # Wait for process to stop
        for i in {1..5}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done

        # Force kill if still running
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️  Process still running, force killing..."
            kill -9 $PID
        fi

        rm -f "$PID_FILE"
        echo "✅ Redis monitor stopped"
    else
        echo "⚠️  Process not running (stale PID file removed)"
        rm -f "$PID_FILE"
    fi
}

status_monitor() {
    echo "📊 Redis Monitor Status"
    echo "======================"

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Status: ✅ Running"
            echo "PID: $PID"
            echo "Port: $PORT"
            echo "Dashboard: http://localhost:$PORT"
            echo "API: http://localhost:$PORT/api/redis-data"
            echo ""

            # Check if port is actually listening
            if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
                echo "Port Status: ✅ Listening"

                # Test API endpoint
                if curl -s -f "http://localhost:$PORT/api/redis-data" > /dev/null 2>&1; then
                    echo "API Status: ✅ Responding"

                    # Get session count
                    SESSIONS=$(curl -s "http://localhost:$PORT/api/redis-data" | python3 -c "import sys, json; print(json.load(sys.stdin)['active_sessions'])" 2>/dev/null)
                    if [ ! -z "$SESSIONS" ]; then
                        echo "Active Sessions: $SESSIONS"
                    fi
                else
                    echo "API Status: ❌ Not responding"
                fi
            else
                echo "Port Status: ❌ Not listening"
            fi

            # Show last log lines
            if [ -f "$LOG_FILE" ]; then
                echo ""
                echo "Recent Logs:"
                tail -5 "$LOG_FILE"
            fi
        else
            echo "Status: ❌ Not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "Status: ❌ Not running"

        # Check if something else is on the port
        PID=$(lsof -ti:$PORT 2>/dev/null)
        if [ ! -z "$PID" ]; then
            echo ""
            echo "⚠️  Warning: Port $PORT is in use by PID $PID"
            ps -p $PID -o pid,comm,args
        fi
    fi
}

restart_monitor() {
    echo "🔄 Restarting Redis monitor..."
    stop_monitor
    sleep 1
    start_monitor
}

open_dashboard() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "🌐 Opening dashboard in browser..."
            if command -v open &> /dev/null; then
                open "http://localhost:$PORT"
            elif command -v xdg-open &> /dev/null; then
                xdg-open "http://localhost:$PORT"
            else
                echo "📊 Dashboard: http://localhost:$PORT"
            fi
        else
            echo "❌ Redis monitor is not running"
            return 1
        fi
    else
        echo "❌ Redis monitor is not running"
        return 1
    fi
}

view_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "📝 Viewing logs (Ctrl+C to exit)..."
        tail -f "$LOG_FILE"
    else
        echo "❌ No log file found at $LOG_FILE"
    fi
}

# Main command handler
case "${1:-}" in
    start)
        start_monitor
        ;;
    stop)
        stop_monitor
        ;;
    restart)
        restart_monitor
        ;;
    status)
        status_monitor
        ;;
    open)
        open_dashboard
        ;;
    logs)
        view_logs
        ;;
    *)
        echo "Redis Monitor Control Script"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|open|logs}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the Redis monitor server"
        echo "  stop     - Stop the Redis monitor server"
        echo "  restart  - Restart the Redis monitor server"
        echo "  status   - Show current status and stats"
        echo "  open     - Open dashboard in browser"
        echo "  logs     - View server logs (real-time)"
        echo ""
        echo "Quick Start:"
        echo "  ./scripts/redis_monitor.sh start"
        echo "  ./scripts/redis_monitor.sh status"
        echo "  ./scripts/redis_monitor.sh open"
        echo ""
        exit 1
        ;;
esac
