#!/bin/bash

# 🚀 Subscription Tracker Backend - Start All Services
# This script starts Redis, Celery Worker, Celery Beat, and FastAPI server

set -e  # Exit on any error

echo "🚀 Starting Subscription Tracker Backend Services"
echo "================================================="

# Check if we're in the right directory
if [ ! -f "src/main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "💡 Expected to find src/main.py in current directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -f "venv/bin/python" ]; then
    echo "❌ Error: Virtual environment not found"
    echo "💡 Please create virtual environment first: python3 -m venv venv"
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a service is running
check_service() {
    if pgrep -f "$1" > /dev/null; then
        echo -e "${GREEN}✅ $2 is already running${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ Starting $2...${NC}"
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    echo -e "${BLUE}⏳ Waiting for $1 to start...${NC}"
    sleep $2
}

# Create logs directory
mkdir -p logs

echo -e "${BLUE}📁 Created logs directory${NC}"

# 1. Start Redis
echo -e "\n${BLUE}1. Starting Redis...${NC}"
if ! check_service "redis-server" "Redis"; then
    if command -v brew &> /dev/null && brew services list | grep redis | grep started > /dev/null; then
        echo -e "${GREEN}✅ Redis already running via Homebrew${NC}"
    elif command -v brew &> /dev/null; then
        brew services start redis
        echo -e "${GREEN}✅ Redis started via Homebrew${NC}"
    else
        echo -e "${RED}❌ Please install and start Redis manually${NC}"
        echo -e "${YELLOW}💡 macOS: brew install redis && brew services start redis${NC}"
        exit 1
    fi
fi

# Test Redis connection
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis connection: OK${NC}"
else
    echo -e "${RED}❌ Redis connection failed${NC}"
    exit 1
fi

# 2. Start Celery Worker
echo -e "\n${BLUE}2. Starting Celery Worker...${NC}"
if ! check_service "celery.*worker" "Celery Worker"; then
    # Kill any existing worker processes
    pkill -f "celery.*worker" 2>/dev/null || true
    
    # Remove old PID file
    rm -f logs/celery_worker.pid
    
    # Start worker in background
    nohup ./venv/bin/celery -A src.infrastructure.celery_app worker \
        --loglevel=INFO \
        --queues=token_refresh \
        --concurrency=2 \
        --logfile=logs/celery_worker.log \
        --pidfile=logs/celery_worker.pid \
        > /dev/null 2>&1 &
    
    wait_for_service "Celery Worker" 3
    echo -e "${GREEN}✅ Celery Worker started${NC}"
fi

# 3. Start Celery Beat
echo -e "\n${BLUE}3. Starting Celery Beat (Scheduler)...${NC}"
if ! check_service "celery.*beat" "Celery Beat"; then
    # Kill any existing beat processes
    pkill -f "celery.*beat" 2>/dev/null || true
    
    # Remove old PID file and schedule DB
    rm -f logs/celery_beat.pid
    rm -f logs/celerybeat-schedule.db
    
    # Start beat in background
    nohup ./venv/bin/celery -A src.infrastructure.celery_app beat \
        --loglevel=INFO \
        --logfile=logs/celery_beat.log \
        --pidfile=logs/celery_beat.pid \
        > /dev/null 2>&1 &
    
    wait_for_service "Celery Beat" 2
    echo -e "${GREEN}✅ Celery Beat started${NC}"
fi

# 4. Verify Celery is working
echo -e "\n${BLUE}4. Verifying Celery setup...${NC}"
if ./venv/bin/celery -A src.infrastructure.celery_app inspect ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Celery workers responding${NC}"
else
    echo -e "${YELLOW}⚠️  Celery workers may still be starting...${NC}"
fi

echo -e "\n${GREEN}🎉 All background services started successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Monitor services with:${NC}"
echo -e "${YELLOW}  • Celery Worker logs: tail -f logs/celery_worker.log${NC}"
echo -e "${YELLOW}  • Celery Beat logs:   tail -f logs/celery_beat.log${NC}"
echo -e "${YELLOW}  • Redis status:       redis-cli ping${NC}"
echo ""

# 5. Start FastAPI Server
echo -e "${BLUE}5. Starting FastAPI Server...${NC}"

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use${NC}"
    echo -e "${BLUE}🔍 Current process on port 8000:${NC}"
    lsof -Pi :8000 -sTCP:LISTEN
    echo ""
    echo -e "${YELLOW}💡 Options:${NC}"
    echo -e "${YELLOW}   1. Kill existing server: pkill -f uvicorn${NC}"
    echo -e "${YELLOW}   2. Use different port: --port 8001${NC}"
    echo -e "${YELLOW}   3. Background services are running successfully!${NC}"
    echo ""
    echo -e "${GREEN}✅ All background services are ready!${NC}"
    echo -e "${BLUE}📊 Monitor with: tail -f logs/celery_worker.log${NC}"
    exit 0
else
    echo -e "${GREEN}🚀 Server starting at: http://localhost:8000${NC}"
    echo -e "${GREEN}📚 API Documentation: http://localhost:8000/api/docs${NC}"
    echo ""
    echo -e "${YELLOW}💡 Use Ctrl+C to stop the server${NC}"
    echo -e "${YELLOW}💡 Background services will continue running${NC}"
    echo ""
    
    # Start the FastAPI server (this will block)
    exec ./venv/bin/uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
fi