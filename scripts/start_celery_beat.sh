#!/bin/bash
# Professional Celery Beat scheduler startup script
# Handles periodic token refresh tasks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}📅 Starting Celery Beat Scheduler${NC}"
echo -e "${YELLOW}================================${NC}"

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
    echo -e "${RED}❌ Error: Redis is not running. Please start Redis first${NC}"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Set environment variables
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/1"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/2"}

echo -e "${GREEN}✅ Redis connection: OK${NC}"
echo -e "${GREEN}✅ Periodic tasks configured:${NC}"
echo -e "${YELLOW}   • Token refresh check: Every 5 minutes${NC}"
echo -e "${YELLOW}   • Cleanup failed tokens: Every hour${NC}"
echo ""

# Start Celery Beat scheduler
echo -e "${GREEN}🔄 Starting Celery Beat scheduler...${NC}"
exec celery -A src.infrastructure.celery_app beat \
    --loglevel=info \
    --logfile=logs/celery_beat.log \
    --pidfile=logs/celery_beat.pid \
    --schedule=logs/celerybeat-schedule