# 🚀 Subscription Tracker Backend API

Professional FastAPI backend for managing subscription tracking across multiple Google accounts with **automated OAuth token refresh** using Celery background tasks.

## 🏗️ Architecture

This project follows **Clean Architecture** principles with a professional folder structure:

```
src/
├── api/                    # API Layer
│   └── v1/                # API version 1
│       ├── endpoints/     # API endpoints
│       └── router.py      # Main API router
├── core/                  # Core utilities
│   ├── config/           # Configuration management
│   ├── logging/          # Logging setup
│   └── security/         # Security utilities
├── database/             # Database layer
│   ├── migrations/       # Alembic migrations
│   └── seeders/          # Database seeders
├── domain/               # Business Logic Layer
│   ├── entities/         # Database models
│   ├── repositories/     # Data repositories
│   └── services/         # Business services
├── infrastructure/       # External services
│   ├── external/         # 3rd party integrations
│   └── storage/          # File/blob storage
├── presentation/         # Presentation Layer
│   ├── middleware/       # HTTP middleware
│   └── responses/        # Response schemas
├── tests/                # Test suites
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
└── scripts/              # Utility scripts

# Root Helper Scripts
start_all_services.sh       # Start Redis + Celery + FastAPI with one command
stop_all_services.sh        # Stop all background services cleanly  
```

## 🚀 Running Locally

### Prerequisites

- Python 3.8+ 
- Git

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd subscription-tracker-backend
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your settings (optional for basic usage)
# The app will work with default SQLite database
```

### Step 5: Database Setup

```bash
# Run database migrations
venv/bin/alembic upgrade head
```

### Step 6: Setup Configuration

Create `.env.local` file with your settings:
```env
# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://username:password@localhost:5432/subscription_tracker

# Redis (Required for Celery background tasks)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production-min-32-chars
ALGORITHM=HS256

# Google OAuth (Required for token refresh)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Step 7: Start All Services

**🚀 Option A: Quick Start (Recommended)**
```bash
# Start everything with one command
./start_all_services.sh
```

**🔧 Option B: Manual Start (For Development)**

**Start services in this order for proper functionality:**

**1. Start Redis (Required for Celery):**
```bash
# macOS with Homebrew
brew services start redis

# Or manually
redis-server
```

**2. Start Celery Worker (Background Token Refresh):**
```bash
# Professional setup with logging - THIS IS CRITICAL
./venv/bin/celery -A src.infrastructure.celery_app worker \
  --loglevel=INFO \
  --queues=token_refresh \
  --concurrency=2 \
  --logfile=logs/celery_worker.log \
  --pidfile=logs/celery_worker.pid
```

**3. Start Celery Beat (Periodic Token Refresh):**
```bash
# Automatic token refresh every 5 minutes
./venv/bin/celery -A src.infrastructure.celery_app beat \
  --loglevel=INFO \
  --logfile=logs/celery_beat.log \
  --pidfile=logs/celery_beat.pid
```

**4. Start FastAPI Server:**
```bash
./venv/bin/uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

### Step 8: Access the Application

- **API Server**: http://localhost:8000
- **Swagger UI Documentation**: http://localhost:8000/api/docs
- **ReDoc Documentation**: http://localhost:8000/api/redoc
- **Health Check**: http://localhost:8000/api/v1/health

## 🔧 Celery Background Tasks - CRITICAL COMPONENT

### **Why Celery is Essential**

This application uses **Celery for automatic OAuth token refresh** - this is **not optional** for production use:

- **✅ Prevents Authentication Failures:** Automatically refreshes tokens before expiry
- **✅ Professional Concurrency Control:** Handles multiple accounts without conflicts  
- **✅ Real Google API Integration:** Makes actual calls to Google OAuth endpoints
- **✅ Database Consistency:** Uses row-level locking to prevent race conditions
- **✅ Enterprise Retry Logic:** Exponential backoff with intelligent error handling

### **Monitor Celery (Essential for Debugging)**

**Real-time Log Monitoring:**
```bash
# Watch worker logs (shows token refresh operations)
tail -f logs/celery_worker.log

# Watch beat logs (shows periodic task scheduling)  
tail -f logs/celery_beat.log

# Live filtering for important events
tail -f logs/celery_worker.log | grep -E "(Starting token refresh|Successfully refreshed|Google API error)"

# Monitor both worker and beat logs simultaneously
tail -f logs/celery_worker.log logs/celery_beat.log
```

**📄 Log Files Explained:**
- **`logs/celery_worker.log`** - Background task execution, token refresh operations
- **`logs/celery_beat.log`** - Periodic task scheduler (sends refresh tasks every 5 minutes)
- **`logs/*.pid`** - Process ID files for service management (auto-created)
- **`logs/celerybeat-schedule.db`** - Beat's internal schedule database (auto-created)

**Check Worker Status:**
```bash
# Verify workers are running
./venv/bin/celery -A src.infrastructure.celery_app inspect active

# Check task queue
./venv/bin/celery -A src.infrastructure.celery_app inspect scheduled

# Worker health check
./venv/bin/celery -A src.infrastructure.celery_app inspect ping
```

**Manual Token Refresh Testing:**
```bash
# Test individual account refresh
./venv/bin/python -c "
from src.infrastructure.tasks.token_refresh import refresh_oauth_token
task = refresh_oauth_token.delay('account-uuid-here')
print(f'Task ID: {task.id}')
print('Check logs/celery_worker.log for results')
"

# Test bulk refresh (production behavior)
./venv/bin/python -c "
from src.infrastructure.tasks.token_refresh import refresh_all_expired_tokens  
result = refresh_all_expired_tokens()
print('Bulk refresh result:', result)
"
```

### **Troubleshooting Celery Issues**

**1. Worker Not Processing Tasks:**
```bash
# Check Redis connection
redis-cli ping
# Should return: PONG

# Restart worker
pkill -f "celery.*worker" 
./venv/bin/celery -A src.infrastructure.celery_app worker --loglevel=INFO --queues=token_refresh --concurrency=2
```

**2. Google OAuth Token Errors:**
```bash
# Verify credentials loaded
./venv/bin/python -c "
from src.core.config.settings import get_settings
s = get_settings()
print('Client ID:', 'SET' if s.GOOGLE_CLIENT_ID else 'NOT SET')
print('Client Secret:', 'SET' if s.GOOGLE_CLIENT_SECRET else 'NOT SET')
"
```

**3. Database Lock Issues:**
```bash
# Check for database lock errors in logs
grep -E "(lock|timeout|SELECT FOR UPDATE)" logs/celery_worker.log
```

### **Log Management:**

**📋 Log File Locations:**
```bash
# All logs are stored in the logs/ directory
logs/
├── .gitkeep                 # Preserves directory in git
├── celery_worker.log        # Background task execution logs
├── celery_beat.log          # Periodic scheduler logs  
├── celery_worker.pid        # Worker process ID (runtime)
├── celery_beat.pid          # Beat process ID (runtime)
└── celerybeat-schedule.db   # Beat's schedule database (runtime)
```

**🧹 Log Cleanup:**
```bash
# Clear all log files (services should be stopped first)
rm -f logs/*.log logs/*.pid logs/celerybeat-schedule.db

# Or use logrotate in production for automatic cleanup
```

### **Stop All Services:**

**🛑 Quick Stop:**
```bash
# Stop all background services
./stop_all_services.sh
```

**🔧 Manual Stop:**
```bash
# Stop Celery services
pkill -f "celery.*worker"
pkill -f "celery.*beat"

# Stop Redis
brew services stop redis  # macOS

# Stop FastAPI (Ctrl+C in terminal)
```

### API Testing

Test the API endpoints using curl or any API client:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Test authentication endpoint
curl -X POST http://localhost:8000/api/v1/auth/save-user \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "test123",
      "email": "test@example.com", 
      "name": "Test User",
      "image": "https://example.com/avatar.jpg"
    },
    "tokens": {
      "access_token": "test_token",
      "refresh_token": "refresh_token",
      "expires_at": 1700000000
    }
  }'
```

## 🔧 Development Commands

### **🚀 Service Management Scripts:**
```bash
# Start all services (Redis + Celery + FastAPI)
./start_all_services.sh

# Stop all background services  
./stop_all_services.sh
```

### **📊 Monitoring Commands:**
```bash
# Monitor Celery worker logs
tail -f logs/celery_worker.log

# Monitor Celery beat scheduler
tail -f logs/celery_beat.log

# Check worker status
./venv/bin/celery -A src.infrastructure.celery_app inspect active
```

### **⚙️ Development Commands:**
```bash
# Install dependencies
make install

# Run development server
make dev

# Run tests
make test

# Run linting
make lint

# Format code
make format

# Database migrations
make migrate

# Clean temporary files
make clean
```

## 🔑 Key Features

### **🎯 Core Functionality:**
- **Multi-Account Google OAuth**: Support for multiple Google accounts per user
- **Automated Token Refresh**: Professional Celery background task system
- **Real-time Monitoring**: Comprehensive logging and health checks
- **Database Consistency**: Row-level locking prevents race conditions

### **🏗️ Professional Architecture:**  
- **Clean Architecture**: Modular, testable, and maintainable codebase
- **Database Migration**: Automated schema management with Alembic
- **Security First**: AES token encryption, rate limiting, CORS protection
- **Enterprise Patterns**: Professional error handling and retry logic

### **⚡ Performance & Reliability:**
- **Async FastAPI**: High-performance async request handling
- **Connection Pooling**: Optimized database connections
- **Background Tasks**: Non-blocking token refresh operations  
- **Exponential Backoff**: Smart retry logic for failed operations

### **🔧 Developer Experience:**
- **Interactive API Docs**: Swagger/OpenAPI documentation
- **Professional Logging**: Structured logs with request tracing
- **Environment Configuration**: Flexible .env-based settings
- **Docker Support**: Production-ready containerization

## 📚 Documentation

For comprehensive documentation, visit the `/docs` directory:

- **[Complete API Documentation](docs/README.md)** - Enterprise-grade documentation
- **[API Reference](docs/api/v1/comprehensive-api-guide.md)** - Detailed API endpoints
- **[Security Guide](docs/guides/security-monitoring.md)** - Security architecture  
- **[Production Setup](PRODUCTION_READINESS.md)** - Deployment guide

## 🚀 Production-Ready Features

### **🔒 Enterprise Security:**
- **OAuth Token Encryption**: AES encryption for all stored tokens
- **Professional Error Handling**: Structured exceptions with proper HTTP codes
- **Request Validation**: Comprehensive input validation with Pydantic
- **Security Headers**: CORS, rate limiting, and security middleware

### **📊 Monitoring & Observability:**  
- **Structured Logging**: JSON logs with correlation IDs
- **Health Checks**: Database, Redis, and Celery worker monitoring
- **Task Monitoring**: Real-time visibility into background operations
- **Error Tracking**: Comprehensive exception logging and alerting

### **⚙️ Operational Excellence:**
- **Database Migrations**: Zero-downtime schema updates with Alembic  
- **Connection Pooling**: Optimized database connection management
- **Graceful Shutdowns**: Proper cleanup of resources and connections
- **Configuration Management**: Environment-based settings with validation

---

## ✨ Professional OAuth Token Management System

This application implements **enterprise-grade automatic OAuth token refresh**:

🔄 **Background Processing**: Celery workers refresh tokens every 5 minutes  
🔒 **Concurrency Control**: Database row locking prevents race conditions  
🎯 **Smart Scheduling**: Only refreshes tokens expiring within 10 minutes  
⚡ **High Performance**: Non-blocking async operations  
📊 **Full Monitoring**: Comprehensive logging and error tracking  
🛡️ **Error Recovery**: Exponential backoff with intelligent retry logic  

**Your users will never experience authentication interruptions!** 🎉

---

Built with ❤️ using **FastAPI**, **Celery**, **SQLAlchemy**, and **modern Python practices**.