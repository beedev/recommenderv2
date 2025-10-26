#!/bin/bash

# Stop Backend and Frontend Servers

echo "========================================"
echo "Stopping Recommender_v2 Servers"
echo "========================================"

# Kill backend on port 8001
BACKEND_PID=$(lsof -ti:8001)
if [ ! -z "$BACKEND_PID" ]; then
    echo "  Stopping backend on port 8001 (PID: $BACKEND_PID)"
    kill -9 $BACKEND_PID 2>/dev/null
    echo "  ✓ Backend stopped"
else
    echo "  No backend running on port 8001"
fi

# Kill frontend on port 3001
FRONTEND_PID=$(lsof -ti:3001)
if [ ! -z "$FRONTEND_PID" ]; then
    echo "  Stopping frontend on port 3001 (PID: $FRONTEND_PID)"
    kill -9 $FRONTEND_PID 2>/dev/null
    echo "  ✓ Frontend stopped"
else
    echo "  No frontend running on port 3001"
fi

# Kill any remaining processes
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "http.server 300" 2>/dev/null

echo ""
echo "✓ All servers stopped"
echo ""
