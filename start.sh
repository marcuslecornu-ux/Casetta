#!/bin/bash
# Casetta App — Startup Script
# Run this to start the app. It will open in your browser at http://localhost:5050

cd "$(dirname "$0")"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required. Please install it from https://python.org"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -q flask
    echo "Setup complete."
fi

echo ""
echo "  Starting Casetta App..."
echo "  Open your browser at: http://localhost:5050"
echo "  Press Ctrl+C to stop"
echo ""

# Open browser after a short delay
(sleep 1.5 && open http://localhost:5050) &

.venv/bin/python app.py
