#!/bin/bash
# Professional Celery worker startup script
# Handles token refresh and background tasks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Celery Worker for Token Management${NC}"
echo -e "${YELLOW}===============================================${NC}"

# Check if we're in the project directory
if [ ! -f "src/infrastructure/celery_app.py" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not detected. Activating...${NC}"
    source venv/bin/activate
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Redis is not running. Please start Redis first:${NC}"
    echo -e "${YELLOW}   brew services start redis${NC}"
    echo -e "${YELLOW}   # or${NC}"
    echo -e "${YELLOW}   redis-server${NC}"
    exit 1
fi

# Set environment variables for production
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/1"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/2"}

echo -e "${GREEN}✅ Redis connection: OK${NC}"
echo -e "${GREEN}✅ Broker: $CELERY_BROKER_URL${NC}"
echo -e "${GREEN}✅ Result Backend: $CELERY_RESULT_BACKEND${NC}"
echo ""

# Start Celery worker with professional configuration
echo -e "${GREEN}🔄 Starting Celery worker...${NC}"
exec celery -A src.infrastructure.celery_app worker \
    --loglevel=info \
    --queues=token_refresh \
    --concurrency=4 \
    --max-tasks-per-child=1000 \
    --time-limit=300 \
    --soft-time-limit=240 \
    --hostname=worker-token-refresh@%h \
    --logfile=logs/celery_worker.log \
    --pidfile=logs/celery_worker.pid