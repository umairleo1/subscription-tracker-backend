#!/bin/bash

# Subscription Tracker Backend - Development Server Startup
echo "Starting Subscription Tracker Backend API..."
echo "Environment: Development"
echo "Port: 8000"
echo ""

# Activate virtual environment and start server
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --log-level info