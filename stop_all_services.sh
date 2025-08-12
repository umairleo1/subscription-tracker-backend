#!/bin/bash

# 🛑 Subscription Tracker Backend - Stop All Services
# This script stops Celery Worker, Celery Beat, and optionally Redis

set -e

echo "🛑 Stopping Subscription Tracker Backend Services"
echo "================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Stop Celery Worker
echo -e "${BLUE}1. Stopping Celery Worker...${NC}"
if pgrep -f "celery.*worker" > /dev/null; then
    # Try graceful shutdown first
    if [ -f "logs/celery_worker.pid" ]; then
        kill $(cat logs/celery_worker.pid) 2>/dev/null || true
        sleep 2
    fi
    
    # Force kill if still running
    pkill -f "celery.*worker" 2>/dev/null || true
    rm -f logs/celery_worker.pid
    echo -e "${GREEN}✅ Celery Worker stopped${NC}"
else
    echo -e "${YELLOW}⚠️  Celery Worker was not running${NC}"
fi

# 2. Stop Celery Beat
echo -e "\n${BLUE}2. Stopping Celery Beat...${NC}"
if pgrep -f "celery.*beat" > /dev/null; then
    # Try graceful shutdown first
    if [ -f "logs/celery_beat.pid" ]; then
        kill $(cat logs/celery_beat.pid) 2>/dev/null || true
        sleep 2
    fi
    
    # Force kill if still running
    pkill -f "celery.*beat" 2>/dev/null || true
    rm -f logs/celery_beat.pid
    rm -f logs/celerybeat-schedule.db
    echo -e "${GREEN}✅ Celery Beat stopped${NC}"
else
    echo -e "${YELLOW}⚠️  Celery Beat was not running${NC}"
fi

# 3. Stop FastAPI Server
echo -e "\n${BLUE}3. Stopping FastAPI Server...${NC}"
if pgrep -f "uvicorn.*src.main:app" > /dev/null; then
    pkill -f "uvicorn.*src.main:app" 2>/dev/null || true
    echo -e "${GREEN}✅ FastAPI Server stopped${NC}"
else
    echo -e "${YELLOW}⚠️  FastAPI Server was not running${NC}"
fi

# 4. Optional: Stop Redis
echo -e "\n${BLUE}4. Redis status...${NC}"
if command -v brew &> /dev/null && brew services list | grep redis | grep started > /dev/null; then
    echo -e "${YELLOW}ℹ️  Redis is running via Homebrew${NC}"
    echo -e "${BLUE}💡 To stop Redis: brew services stop redis${NC}"
elif pgrep -f "redis-server" > /dev/null; then
    echo -e "${YELLOW}ℹ️  Redis is running (manual start)${NC}"
    echo -e "${BLUE}💡 To stop Redis: pkill redis-server${NC}"
else
    echo -e "${GREEN}ℹ️  Redis is not running${NC}"
fi

echo -e "\n${GREEN}✅ Background services stopped successfully!${NC}"
echo ""
echo -e "${BLUE}📊 To verify services are stopped:${NC}"
echo -e "${YELLOW}  • Check processes: ps aux | grep celery${NC}"
echo -e "${YELLOW}  • Check Redis:     redis-cli ping${NC}"
echo ""
echo -e "${GREEN}🚀 To restart services: ./start_all_services.sh${NC}"