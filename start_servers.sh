#!/bin/bash

# Start/Restart Backend and Frontend Servers
# Backend: Port 8001
# Frontend: Port 3001

echo "========================================"
echo "Starting Recommender_v2 Servers"
echo "========================================"

# Kill existing processes
echo ""
echo "Stopping existing servers..."

# Kill backend on port 8001
BACKEND_PID=$(lsof -ti:8001)
if [ ! -z "$BACKEND_PID" ]; then
    echo "  Killing backend process on port 8001 (PID: $BACKEND_PID)"
    kill -9 $BACKEND_PID 2>/dev/null
fi

# Kill frontend on port 3001
FRONTEND_PID=$(lsof -ti:3001)
if [ ! -z "$FRONTEND_PID" ]; then
    echo "  Killing frontend process on port 3001 (PID: $FRONTEND_PID)"
    kill -9 $FRONTEND_PID 2>/dev/null
fi

# Also kill any remaining uvicorn or http.server processes
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "http.server 300" 2>/dev/null

echo "  ✓ Existing servers stopped"

# Wait a moment for ports to be released
sleep 2

# Start backend
echo ""
echo "Starting backend server (port 8001)..."
cd backend
source venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "  ✓ Backend started (PID: $BACKEND_PID)"
echo "  Logs: backend.log"
cd ..

# Wait for backend to initialize
sleep 3

# Start frontend
echo ""
echo "Starting frontend server (port 3001)..."
nohup python3 -m http.server 3001 > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  ✓ Frontend started (PID: $FRONTEND_PID)"
echo "  Logs: frontend.log"

# Display server info
echo ""
echo "========================================"
echo "Servers Started Successfully!"
echo "========================================"
echo ""
echo "Backend API:"
echo "  URL: http://localhost:8001"
echo "  Docs: http://localhost:8001/docs"
echo "  Health: http://localhost:8001/health"
echo ""
echo "Frontend:"
echo "  URL: http://localhost:3001"
echo "  Test UI: http://localhost:3001/test_extraction.html"
echo ""
echo "Logs:"
echo "  Backend: tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
echo "To stop servers:"
echo "  ./stop_servers.sh"
echo ""
