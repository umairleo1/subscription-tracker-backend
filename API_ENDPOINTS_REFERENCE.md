# Subscription Tracker API - Complete Endpoints Reference

## Base URL
```
http://localhost:8000/api/v1
```

## API Documentation
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## 🏥 Health & Monitoring Endpoints

### Health Check
```http
GET /api/v1/health
```
**Description**: Basic API health check  
**Response**: `200 OK`
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### Detailed Health Check
```http
GET /api/v1/monitoring/health
```
**Description**: Basic monitoring health check  
**Response**: `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2025-08-10T10:30:00Z",
  "service": "subscription-tracker-api",
  "version": "1.0.0"
}
```

### System Health Check
```http
GET /api/v1/monitoring/health/detailed
```
**Description**: Detailed system health with database and resource checks  
**Response**: `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2025-08-10T10:30:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "system": {
      "status": "healthy",
      "metrics": {
        "cpu_usage_percent": 15.2,
        "memory_usage_percent": 45.8,
        "memory_available_gb": 8.5,
        "disk_usage_percent": 62.1,
        "disk_free_gb": 120.3
      }
    }
  }
}
```

### System Metrics
```http
GET /api/v1/monitoring/metrics
```
**Description**: Get system and application metrics  
**Response**: `200 OK`
```json
{
  "timestamp": "2025-08-10T10:30:00Z",
  "metrics": {
    "users": {
      "total_users": 1250,
      "active_users": 980
    },
    "subscriptions": {
      "total_subscriptions": 3420,
      "active_subscriptions": 2890,
      "trial_subscriptions": 150
    },
    "email_processing": {
      "total_emails_processed": 15678,
      "successful_processing": 14892,
      "failed_processing": 786,
      "success_rate": 94.98
    },
    "notifications": {
      "total_notifications": 8945,
      "sent_notifications": 8234,
      "pending_notifications": 45
    },
    "connected_accounts": {
      "total_connected_accounts": 1890,
      "google_accounts": 1890
    }
  }
}
```

### Processing Statistics
```http
GET /api/v1/monitoring/stats/processing
```
**Description**: Get email processing statistics for the last 7 days  
**Response**: `200 OK`

### Financial Statistics
```http
GET /api/v1/monitoring/stats/financial
```
**Description**: Get platform-wide financial statistics  
**Response**: `200 OK`

---

## 🔐 Authentication Endpoints

### Save User (OAuth Integration)
```http
POST /api/v1/auth/save-user
```
**Description**: Save or update user from Google OAuth authentication (NextAuth.js integration)  
**Request Body**:
```json
{
  "profile": {
    "id": "1234567890",
    "email": "user@example.com",
    "given_name": "John",
    "family_name": "Doe",
    "name": "John Doe",
    "picture": "https://lh3.googleusercontent.com/a/photo.jpg"
  },
  "tokens": {
    "access_token": "ya29.a0ARrdaM...",
    "refresh_token": "1//04-refreshtoken",
    "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJS...",
    "expires_at": 1700000000,
    "token_type": "Bearer",
    "scope": "openid email profile"
  },
  "is_primary": true
}
```
**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "user": {
      "id": 1,
      "email": "user@example.com",
      "name": "John Doe",
      "accounts": [...]
    },
    "account_created": true,
    "is_new_user": false
  },
  "message": "User profile and tokens updated successfully"
}
```

### Unlink Google Account
```http
DELETE /api/v1/auth/accounts/{account_id}
```
**Description**: Unlink a secondary Google account (primary accounts cannot be unlinked)  
**Path Parameters**:
- `account_id` (integer): ID of the Google account to unlink

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "unlinked_account": {
      "id": 123,
      "email": "secondary@example.com",
      "was_primary": false
    },
    "user": {
      "id": 1,
      "email": "user@example.com",
      "accounts": [...]
    }
  },
  "message": "Google account unlinked successfully"
}
```

---

## 👤 User Management Endpoints

### Create/Update Primary User
```http
POST /api/v1/users/
```
**Description**: Create or upsert primary user on first Google OAuth sign-in  
**Request Body**:
```json
{
  "profile": {
    "id": "1234567890",
    "email": "user@example.com",
    "given_name": "John",
    "family_name": "Doe",
    "name": "John Doe",
    "picture": "https://lh3.googleusercontent.com/a/photo.jpg"
  },
  "tokens": {
    "access_token": "ya29.a0ARrdaM...",
    "refresh_token": "1//04-refreshtoken",
    "expires_at": 1700000000
  }
}
```
**Response**: `201 Created`

### Get User with Accounts
```http
GET /api/v1/users/{user_id}
```
**Description**: Retrieve user data with all linked accounts and token statuses  
**Path Parameters**:
- `user_id` (integer): User ID

**Query Parameters**:
- `include_inactive` (boolean, default: false): Include inactive linked accounts

**Headers**: `Authorization: Bearer <token>` (requires authentication)

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "linked_accounts": [
      {
        "id": 1,
        "email": "user@example.com",
        "is_primary": true,
        "token_status": "active",
        "needs_reauth": false,
        "expires_at": "2025-08-10T15:30:00Z"
      }
    ]
  },
  "message": "User data retrieved successfully"
}
```

### Link Secondary Account
```http
POST /api/v1/users/{user_id}/linked-accounts
```
**Description**: Link a new secondary Google account to existing user  
**Path Parameters**:
- `user_id` (integer): User ID

**Headers**: `Authorization: Bearer <token>`

**Request Body**:
```json
{
  "profile": {
    "id": "9876543210",
    "email": "secondary@example.com",
    "name": "John Doe Secondary"
  },
  "tokens": {
    "access_token": "ya29.secondary...",
    "refresh_token": "1//04-secondary",
    "expires_at": 1700000000
  }
}
```
**Response**: `201 Created`

### Unlink Secondary Account
```http
DELETE /api/v1/users/{user_id}/linked-accounts/{account_id}
```
**Description**: Unlink a secondary Google account (primary account cannot be unlinked)  
**Path Parameters**:
- `user_id` (integer): User ID
- `account_id` (integer): Account ID to unlink

**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "account_id": 123,
    "status": "unlinked"
  },
  "message": "Account unlinked successfully"
}
```

### Update Account Tokens
```http
PATCH /api/v1/users/{user_id}/linked-accounts/{account_id}/tokens
```
**Description**: Update stored tokens after successful token refresh  
**Path Parameters**:
- `user_id` (integer): User ID
- `account_id` (integer): Account ID

**Headers**: `Authorization: Bearer <token>`

**Request Body**:
```json
{
  "access_token": "ya29.new_token...",
  "refresh_token": "1//04-new-refresh",
  "expires_at": 1700000000,
  "token_type": "Bearer"
}
```
**Response**: `200 OK`

### Mark Re-authentication Complete
```http
PATCH /api/v1/users/{user_id}/linked-accounts/{account_id}/reauth
```
**Description**: Mark account as re-authenticated after OAuth re-consent  
**Path Parameters**:
- `user_id` (integer): User ID
- `account_id` (integer): Account ID

**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "account_id": 123,
    "status": "reauth_complete"
  },
  "message": "Account marked as re-authenticated"
}
```

---

## 📊 Subscription Management Endpoints

### Create Subscription
```http
POST /api/v1/subscriptions/
```
**Description**: Create a new subscription  
**Headers**: `Authorization: Bearer <token>`

**Request Body**:
```json
{
  "service_name": "Netflix",
  "cost": 15.99,
  "billing_cycle": "monthly",
  "next_billing_date": "2025-09-10",
  "category": "Entertainment"
}
```
**Response**: `201 Created`

### Get User Subscriptions
```http
GET /api/v1/subscriptions/
```
**Description**: Get all user subscriptions with optional status filter  
**Headers**: `Authorization: Bearer <token>`

**Query Parameters**:
- `status` (string): Filter by subscription status (active, cancelled, trial, expired)

**Response**: `200 OK`
```json
[
  {
    "id": 1,
    "service_name": "Netflix",
    "cost": 15.99,
    "billing_cycle": "monthly",
    "status": "active",
    "next_billing_date": "2025-09-10T00:00:00Z",
    "category": "Entertainment"
  }
]
```

### Get Subscription Summary
```http
GET /api/v1/subscriptions/summary
```
**Description**: Get user's subscription summary with totals  
**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`
```json
{
  "total_subscriptions": 8,
  "active_subscriptions": 6,
  "monthly_cost": 89.94,
  "annual_cost": 1079.28,
  "upcoming_renewals": 3
}
```

### Get Subscription Insights
```http
GET /api/v1/subscriptions/insights
```
**Description**: Get personalized subscription insights and recommendations  
**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`

### Get Upcoming Renewals
```http
GET /api/v1/subscriptions/upcoming-renewals
```
**Description**: Get subscriptions with upcoming renewals  
**Headers**: `Authorization: Bearer <token>`

**Query Parameters**:
- `days` (integer, default: 7): Number of days to look ahead (1-365)

**Response**: `200 OK`

### Get Single Subscription
```http
GET /api/v1/subscriptions/{subscription_id}
```
**Description**: Get specific subscription details  
**Path Parameters**:
- `subscription_id` (integer): Subscription ID

**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`

### Update Subscription
```http
PUT /api/v1/subscriptions/{subscription_id}
```
**Description**: Update subscription details  
**Path Parameters**:
- `subscription_id` (integer): Subscription ID

**Headers**: `Authorization: Bearer <token>`

**Request Body**:
```json
{
  "cost": 19.99,
  "next_billing_date": "2025-09-15"
}
```
**Response**: `200 OK`

### Cancel Subscription
```http
POST /api/v1/subscriptions/{subscription_id}/cancel
```
**Description**: Cancel a subscription  
**Path Parameters**:
- `subscription_id` (integer): Subscription ID

**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`

### Delete Subscription
```http
DELETE /api/v1/subscriptions/{subscription_id}
```
**Description**: Permanently delete a subscription  
**Path Parameters**:
- `subscription_id` (integer): Subscription ID

**Headers**: `Authorization: Bearer <token>`

**Response**: `204 No Content`

### Mark Usage Detected
```http
POST /api/v1/subscriptions/{subscription_id}/usage
```
**Description**: Mark that subscription usage was detected  
**Path Parameters**:
- `subscription_id` (integer): Subscription ID

**Headers**: `Authorization: Bearer <token>`

**Response**: `204 No Content`

---

## 📈 Analytics Endpoints

### Get Spending Analytics
```http
GET /api/v1/analytics/spending
```
**Description**: Get comprehensive spending analytics  
**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`
```json
{
  "total_monthly": 89.94,
  "total_annual": 1079.28,
  "by_category": {
    "Entertainment": 35.98,
    "Productivity": 25.99,
    "Cloud Storage": 15.99
  },
  "by_billing_cycle": {
    "monthly": 65.95,
    "annual": 299.88
  }
}
```

### Get Spending Trends
```http
GET /api/v1/analytics/trends
```
**Description**: Get spending trends over time  
**Headers**: `Authorization: Bearer <token>`

**Query Parameters**:
- `months` (integer, default: 12): Number of months to analyze (3-24)

**Response**: `200 OK`

### Get Usage Analytics
```http
GET /api/v1/analytics/usage
```
**Description**: Get subscription usage analytics  
**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`

### Get Potential Savings
```http
GET /api/v1/analytics/savings
```
**Description**: Get potential savings from cancelled subscriptions  
**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`

### Get Notification Analytics
```http
GET /api/v1/analytics/notifications
```
**Description**: Get notification delivery and engagement analytics  
**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`

### Get Comprehensive Report
```http
GET /api/v1/analytics/report
```
**Description**: Get comprehensive analytics report  
**Headers**: `Authorization: Bearer <token>`

**Response**: `200 OK`

---

## 🔒 Security Features

### Rate Limiting
All endpoints are protected by multi-layer rate limiting:
- **Authentication endpoints**: 10 requests/minute
- **User endpoints**: 30 requests/minute  
- **General endpoints**: 60 requests/minute

### Rate Limit Headers
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1628784000
```

### Authentication
Most endpoints require Bearer token authentication:
```http
Authorization: Bearer <your_jwt_token>
```

### CORS Support
The API supports Cross-Origin Resource Sharing (CORS) with configured origins.

---

## 📋 Response Format

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully",
  "timestamp": "2025-08-10T10:30:00Z"
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": { ... }
  },
  "timestamp": "2025-08-10T10:30:00Z"
}
```

### Common HTTP Status Codes
- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `409` - Conflict
- `422` - Validation Error
- `429` - Rate Limited
- `500` - Internal Server Error

---

## 🧪 Testing the API

### Using curl
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Create user (NextAuth.js integration)
curl -X POST http://localhost:8000/api/v1/auth/save-user \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "test123",
      "email": "test@example.com",
      "name": "Test User"
    },
    "tokens": {
      "access_token": "test_token",
      "refresh_token": "refresh_token",
      "expires_at": 1700000000
    }
  }'

# Get user data (requires authentication)
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/users/1
```

### Using Python requests
```python
import requests

# Health check
response = requests.get("http://localhost:8000/api/v1/health")
print(response.json())

# Create user
user_data = {
    "profile": {
        "id": "test123",
        "email": "test@example.com",
        "name": "Test User"
    },
    "tokens": {
        "access_token": "test_token",
        "refresh_token": "refresh_token",
        "expires_at": 1700000000
    }
}

response = requests.post(
    "http://localhost:8000/api/v1/auth/save-user",
    json=user_data
)
print(response.json())
```

---

## 🔗 Related Documentation

- **[Complete API Guide](docs/api/v1/comprehensive-api-guide.md)** - Detailed API documentation
- **[Security Guide](docs/guides/security-monitoring.md)** - Security implementation details
- **[Production Setup](PRODUCTION_READINESS.md)** - Production deployment guide
- **[NextAuth.js Integration](docs/guides/nextauth-integration.md)** - Frontend integration guide

This reference covers all available API endpoints as of version 1.0.0. For the most up-to-date API documentation, visit the interactive Swagger UI at `/api/docs`.