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

## 🎯 **Complete API Documentation**

### ✅ **User Management API - Production Ready**

All endpoints now consolidated under `/api/v1/users/` with complete Google OAuth functionality:

---

#### **🔥 1. Create or Update User (Primary Endpoint)**

**Endpoint:** `POST /api/v1/users/`

**Purpose:** Handle both new user creation and linking additional Google accounts with complete Google OAuth integration.

**Request Body:**
```json
{
  "profile": {
    "id": "1234567890",
    "email": "user@example.com", 
    "name": "John Doe",
    "image": "https://lh3.googleusercontent.com/a/photo.jpg"
  },
  "tokens": {
    "access_token": "ya29.access_token_here",
    "refresh_token": "1//refresh_token_here", 
    "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "expires_at": 1700000000,
    "token_type": "Bearer",
    "scope": "openid email profile"
  },
  "is_primary": true
}
```

**Response (201 Created):**
```json
{
  "status": "success",
  "message": "New user created and Google account linked successfully",
  "data": {
    "user": {
      "id": "uuid-here",
      "email": "user@example.com",
      "name": "John Doe", 
      "picture": "https://lh3.googleusercontent.com/a/photo.jpg",
      "is_active": true,
      "subscription_plan": "free",
      "subscription_status": "active",
      "primary_account": {
        "id": "account-uuid",
        "google_id": "1234567890",
        "email": "user@example.com",
        "is_primary": true,
        "token_status": "active",
        "needs_reauth": false
      },
      "secondary_accounts": [],
      "total_accounts": 1,
      "active_accounts": 1,
      "expired_tokens": 0
    },
    "is_new_user": true,
    "account_created": true
  },
  "timestamp": "2025-08-12T19:30:00.000Z"
}
```

**Features:**
- ✅ **Complete OAuth Flow**: Handles Google profile + tokens
- ✅ **Automatic Token Encryption**: AES-256 encryption for stored tokens  
- ✅ **Duplicate Prevention**: Smart handling of existing accounts
- ✅ **Account Limits**: Enforces 5 account maximum per user
- ✅ **Background Token Refresh**: Automatic Celery integration

---

#### **🔥 2. Get Current User**

**Endpoint:** `GET /api/v1/users/me`

**Purpose:** Get authenticated user's complete profile with all linked accounts.

**Query Parameters:**
- `include_inactive` (bool, default: false) - Include inactive accounts

**Headers:**
```
Authorization: Bearer <your-jwt-token>
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Current user data retrieved successfully",
  "data": {
    "id": "user-uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "is_active": true,
    "subscription_plan": "free", 
    "subscription_status": "active",
    "primary_account": {
      "id": "account-uuid",
      "google_id": "1234567890",
      "email": "user@example.com",
      "name": "John Doe",
      "is_primary": true,
      "token_status": "active",
      "needs_reauth": false,
      "is_token_expired": false,
      "connected_at": "2025-08-12T10:00:00.000Z",
      "last_token_refresh": "2025-08-12T18:30:00.000Z"
    },
    "secondary_accounts": [
      {
        "id": "secondary-uuid",
        "google_id": "0987654321", 
        "email": "secondary@example.com",
        "is_primary": false,
        "token_status": "active"
      }
    ],
    "total_accounts": 2,
    "active_accounts": 2,
    "expired_tokens": 0,
    "created_at": "2025-08-12T10:00:00.000Z",
    "last_login_at": "2025-08-12T19:30:00.000Z"
  }
}
```

---

#### **🔥 3. Get User by ID**

**Endpoint:** `GET /api/v1/users/{user_id}`

**Purpose:** Retrieve specific user data (authorization required - users can only access their own data).

**Path Parameters:**
- `user_id` (string) - UUID of the user

**Query Parameters:**
- `include_inactive` (bool, default: false) - Include inactive accounts

**Response:** Same as `/users/me` endpoint

**Security:** Users can only access their own data (403 Forbidden otherwise)

---

#### **🔥 4. Link Secondary Google Account** 

**Endpoint:** `POST /api/v1/users/{user_id}/linked-accounts`

**Purpose:** Link additional Google accounts to existing user (up to 5 total).

**Request Body:**
```json
{
  "profile": {
    "id": "0987654321",
    "email": "secondary@example.com",
    "name": "Jane Smith", 
    "picture": "https://lh3.googleusercontent.com/b/photo.jpg"
  },
  "tokens": {
    "access_token": "ya29.secondary_access_token",
    "refresh_token": "1//secondary_refresh_token",
    "expires_at": 1700000000,
    "token_type": "Bearer"
  }
}
```

**Response (201 Created):**
```json
{
  "status": "success", 
  "message": "Account linked successfully",
  "data": {
    "user": {
      "id": "user-uuid",
      "email": "user@example.com",
      "total_accounts": 2,
      "active_accounts": 2
    },
    "linked_account": {
      "id": "new-account-uuid",
      "google_id": "0987654321",
      "email": "secondary@example.com", 
      "is_primary": false,
      "token_status": "active"
    },
    "is_new_account": true
  }
}
```

**Business Rules:**
- ✅ **Account Limit**: Maximum 5 Google accounts per user
- ✅ **Duplicate Prevention**: Prevents linking same Google account twice
- ✅ **Cross-User Protection**: Prevents linking accounts already used by other users

---

#### **🔥 5. Unlink Secondary Account**

**Endpoint:** `DELETE /api/v1/users/{user_id}/linked-accounts/{account_id}`

**Purpose:** Remove a secondary Google account (protects primary account from deletion).

**Path Parameters:**
- `user_id` (string) - UUID of the user
- `account_id` (string) - UUID of the account to unlink

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Account unlinked successfully", 
  "data": {
    "unlinked_account": {
      "id": "account-uuid",
      "email": "secondary@example.com",
      "was_primary": false
    },
    "user": {
      "id": "user-uuid", 
      "email": "user@example.com",
      "total_accounts": 1,
      "active_accounts": 1,
      "primary_account": {
        "email": "user@example.com"
      },
      "secondary_accounts": []
    }
  }
}
```

**Protection:** Cannot unlink primary account (prevents user lockout)

---

#### **🔥 6. Update Account Tokens**

**Endpoint:** `PATCH /api/v1/users/{user_id}/linked-accounts/{account_id}/tokens`

**Purpose:** Update OAuth tokens after successful refresh (used by frontend or Celery).

**Request Body:**
```json
{
  "access_token": "ya29.new_access_token",
  "refresh_token": "1//new_refresh_token", 
  "expires_at": 1700003600,
  "token_type": "Bearer"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Tokens updated successfully",
  "data": {
    "account_id": "account-uuid",
    "token_status": "active",
    "expires_at": "2025-08-12T20:00:00.000Z",
    "last_token_refresh": "2025-08-12T19:30:00.000Z",
    "message": "Tokens updated successfully"
  }
}
```

**Security:** 
- ✅ **AES Encryption**: All tokens encrypted before storage
- ✅ **Automatic Status Updates**: Updates token expiry status
- ✅ **User Authorization**: Only account owners can update

---

#### **🔥 7. Mark Account Re-authenticated** 

**Endpoint:** `PATCH /api/v1/users/{user_id}/linked-accounts/{account_id}/reauth`

**Purpose:** Mark account as re-authenticated after user completes OAuth re-consent flow.

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Account marked as re-authenticated",
  "data": {
    "account_id": "account-uuid", 
    "status": "reauth_complete"
  }
}
```

**Use Case:** When `needs_reauth: true` in user data, frontend redirects user to OAuth flow, then calls this endpoint.

---

### 📊 **Error Responses**

All endpoints use standardized error format:

```json
{
  "status": "error",
  "message": "Human-readable error message",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Profile must include 'id' and 'email' fields",
    "details": {
      "field": "profile.email",
      "provided": null
    }
  },
  "timestamp": "2025-08-12T19:30:00.000Z"
}
```

**Common Error Codes:**
- `VALIDATION_ERROR` (400) - Invalid request data
- `UNAUTHORIZED` (401) - Missing/invalid authentication  
- `FORBIDDEN` (403) - Insufficient permissions
- `RESOURCE_NOT_FOUND` (404) - User/account not found
- `RESOURCE_CONFLICT` (409) - Account already linked, limits exceeded
- `INTERNAL_SERVER_ERROR` (500) - Server errors


---

### 🧪 **API Testing Examples**

Test the production-ready API endpoints:

#### **✅ Health Check**
```bash
curl http://localhost:8000/api/v1/health
```

#### **✅ Create New User**
```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "1234567890",
      "email": "user@example.com", 
      "name": "John Doe",
      "image": "https://lh3.googleusercontent.com/a/photo.jpg"
    },
    "tokens": {
      "access_token": "ya29.access_token_here",
      "refresh_token": "1//refresh_token_here",
      "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
      "expires_at": 1734567890,
      "token_type": "Bearer",
      "scope": "openid email profile"
    },
    "is_primary": true
  }'
```

#### **✅ Get Current User**
```bash
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json"
```

#### **✅ Link Secondary Account**
```bash
curl -X POST http://localhost:8000/api/v1/users/{user_id}/linked-accounts \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "0987654321",
      "email": "secondary@example.com",
      "name": "Jane Smith"
    },
    "tokens": {
      "access_token": "ya29.secondary_token",
      "refresh_token": "1//secondary_refresh",
      "expires_at": 1734567890
    }
  }'
```

#### **✅ Update Account Tokens**
```bash
curl -X PATCH http://localhost:8000/api/v1/users/{user_id}/linked-accounts/{account_id}/tokens \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.new_access_token",
    "refresh_token": "1//new_refresh_token", 
    "expires_at": 1734571490,
    "token_type": "Bearer"
  }'
```

#### **✅ Unlink Account**
```bash
curl -X DELETE http://localhost:8000/api/v1/users/{user_id}/linked-accounts/{account_id} \
  -H "Authorization: Bearer your-jwt-token"
```

**📋 Expected Response Format:**
All successful responses follow this structure:
```json
{
  "status": "success",
  "message": "Operation completed successfully", 
  "data": { /* endpoint-specific data */ },
  "timestamp": "2025-08-12T19:30:00.000Z"
}
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