#!/bin/bash

# Terminate background processes if script is interrupted
cleanup() {
    echo -e "\nStopping FastAPI server..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Start uvicorn server in the background
echo "Starting FastAPI server on port 5050..."
uvicorn main:app --port 5050 --reload &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to spin up..."
sleep 3

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    echo "FastAPI server is running (PID: $SERVER_PID)."
else
    echo "Error: FastAPI server failed to start."
    exit 1
fi

# Run the call trigger script
python make_call.py

# Clean up
cleanup
