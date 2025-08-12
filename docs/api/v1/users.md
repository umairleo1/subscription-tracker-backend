# User Management API Documentation

## Overview

The User Management API handles primary user creation, linked account management, and OAuth token lifecycle with enterprise-grade security. All operations include encrypted token storage, comprehensive audit logging, and advanced rate limiting with IP reputation tracking.

## 🔐 Security Features

### OAuth Token Encryption
- All tokens encrypted with **AES-128 + PBKDF2** before database storage
- Secure key derivation using environment-based encryption keys
- PII filtering in logs and monitoring systems

### Authorization Model
- **Strict user-scoped access**: Users can only manage their own accounts
- **Primary account protection**: Cannot unlink the primary account
- **Account limits**: Maximum 5 linked Google accounts per user

### Rate Limiting
Advanced multi-layer rate limiting with progressive penalties:

| Endpoint Category | Per Minute | Per Hour | Burst | Penalty Multiplier |
|-------------------|------------|----------|-------|-------------------|
| User Creation | 10 | 100 | 5 | 2.0x |
| User Management | 30 | 500 | 10 | 1.5x |
| Token Operations | 5 | 50 | 2 | 3.0x |

**Rate Limit Headers:**
- `X-RateLimit-Limit-Minute` / `X-RateLimit-Remaining-Minute`
- `X-RateLimit-Limit-Hour` / `X-RateLimit-Remaining-Hour`  
- `X-RateLimit-Reputation-Penalty` (if IP has violations)

## 📋 API Endpoints

### 1. Create or Upsert User

Create a primary user on first sign-in or update existing user tokens.

**Endpoint:** `POST /api/v1/users/`  
**Rate Limit:** 10 requests/minute  
**Authentication:** Not required (registration endpoint)

**Response (200 - Success):**
```json
{
  "status": "success",
  "message": "User profile retrieved successfully",
  "data": {
    "id": 1,
    "email": "user@gmail.com",
    "name": "John Doe", 
    "picture": "https://lh3.googleusercontent.com/a/example",
    "is_active": true,
    "created_at": "2025-08-08T13:48:49.000Z",
    "updated_at": "2025-08-08T14:30:21.000Z",
    "last_login_at": "2025-08-08T15:22:33.000Z",
    "primary_account": {
      "id": 1,
      "google_id": "123456789012345678901",
      "email": "user@gmail.com",
      "name": "John Doe",
      "picture": "https://lh3.googleusercontent.com/a/example",
      "is_primary": true,
      "is_active": true,
      "created_at": "2025-08-08T13:48:49.000Z",
      "updated_at": "2025-08-08T14:30:21.000Z", 
      "last_login_at": "2025-08-08T15:22:33.000Z",
      "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
      "token_expires_at": "2025-08-08T16:22:33.000Z",
      "is_token_expired": false
    },
    "secondary_accounts": [
      {
        "id": 2,
        "google_id": "987654321098765432109",
        "email": "secondary@gmail.com",
        "name": "John Doe Work",
        "picture": "https://lh3.googleusercontent.com/a/work",
        "is_primary": false,
        "is_active": true,
        "created_at": "2025-08-08T14:15:30.000Z",
        "updated_at": "2025-08-08T14:15:30.000Z",
        "last_login_at": "2025-08-08T14:15:30.000Z",
        "scope": "openid email profile",
        "token_expires_at": "2025-08-08T15:15:30.000Z",
        "is_token_expired": true
      }
    ],
    "total_accounts": 2,
    "account_summary": {
      "total_accounts": 2,
      "active_accounts": 2,
      "expired_tokens": 1,
      "has_primary_account": true
    }
  },
  "error": null,
  "meta": null,
  "pagination": null,
  "timestamp": "2025-08-08T15:25:44.000Z",
  "request_id": "uuid-here"
}
```

**Account Summary Fields:**
- `total_accounts`: Total number of linked Google accounts
- `active_accounts`: Number of active accounts (not disabled)
- `expired_tokens`: Number of accounts with expired tokens
- `has_primary_account`: Whether user has a primary account

**Error Responses:**

*400 - Invalid User ID:*
```json
{
  "status": "error",
  "message": "Invalid user ID",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {}
  }
}
```

*403 - Inactive User:*
```json
{
  "status": "error",
  "message": "User account is inactive",
  "error": {
    "code": "FORBIDDEN",
    "details": {
      "user_id": 1
    }
  }
}
```

*404 - User Not Found:*
```json
{
  "status": "error",
  "message": "User not found (ID: 999)",
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "details": {
      "resource": "User",
      "resource_id": "999" 
    }
  }
}
```

### Get User by ID (Admin Access)
Retrieve any user's profile by their ID. Intended for admin or authorized access only.

**Endpoint:** `GET /users/{user_id}`

**Description:**
Allows retrieving any user's profile by their ID. In production, this should be restricted to the user themselves or system administrators. Sensitive token information is excluded from the response.

**Path Parameters:**
- `user_id` (integer): The ID of the user to retrieve

**Response (200 - Success):**
```json
{
  "status": "success",
  "message": "User profile retrieved successfully",
  "data": {
    "id": 1,
    "email": "user@gmail.com",
    "name": "John Doe",
    "picture": "https://lh3.googleusercontent.com/a/example",
    "is_active": true,
    "created_at": "2025-08-08T13:48:49.000Z",
    "updated_at": "2025-08-08T14:30:21.000Z",
    "last_login_at": "2025-08-08T15:22:33.000Z",
    "primary_account": {
      "id": 1,
      "google_id": "123456789012345678901",
      "email": "user@gmail.com",
      "name": "John Doe",
      "picture": "https://lh3.googleusercontent.com/a/example",
      "is_primary": true,
      "is_active": true,
      "created_at": "2025-08-08T13:48:49.000Z",
      "updated_at": "2025-08-08T14:30:21.000Z",
      "last_login_at": "2025-08-08T15:22:33.000Z",
      "scope": "openid email profile",
      "token_expires_at": "2025-08-08T16:22:33.000Z",
      "is_token_expired": false
      // Note: access_token, refresh_token, and id_token are excluded for security
    },
    "secondary_accounts": [
      // Secondary accounts with sensitive data excluded
    ],
    "total_accounts": 2
  }
}
```

**Security Notes:**
- Sensitive token data (access_token, refresh_token, id_token) are excluded
- Should require admin authorization in production
- Rate limited to prevent abuse

## Usage Examples

### Example 1: Get Current User Profile
```bash
# Development (with user_id parameter)
curl -X GET "http://localhost:8000/api/v1/users/me?user_id=1" \
  -H "Accept: application/json"

# Production (with authentication header)
curl -X GET http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer your-jwt-token" \
  -H "Accept: application/json"
```

### Example 2: Get User by ID (Admin)
```bash
curl -X GET http://localhost:8000/api/v1/users/1 \
  -H "Authorization: Bearer admin-jwt-token" \
  -H "Accept: application/json"
```

### Example 3: Check Account Status
```bash
# Get user profile and check account summary
curl -s http://localhost:8000/api/v1/users/me?user_id=1 | \
  jq '.data.account_summary'

# Output:
{
  "total_accounts": 2,
  "active_accounts": 2,
  "expired_tokens": 1,
  "has_primary_account": true
}
```

## Response Field Descriptions

### User Profile Fields
- `id`: Unique user identifier
- `email`: Primary email address (from primary Google account)
- `name`: Display name (from Google profile)
- `picture`: Profile picture URL (from Google)
- `is_active`: Whether user account is active
- `created_at`: When user was first created
- `updated_at`: Last profile update timestamp
- `last_login_at`: Most recent login timestamp

### Google Account Fields
- `id`: Unique account identifier in our system
- `google_id`: Google's unique user identifier
- `email`: Google account email address
- `name`: Display name from this Google account
- `picture`: Profile picture from this Google account
- `is_primary`: Whether this is the primary account
- `is_active`: Whether this account is active
- `scope`: OAuth scopes granted for this account
- `token_expires_at`: When the access token expires
- `is_token_expired`: Whether the token is currently expired

## Frontend Integration

### React Example
```javascript
// hooks/useCurrentUser.js
import { useState, useEffect } from 'react'

export function useCurrentUser() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchUser() {
      try {
        const response = await fetch('/api/v1/users/me', {
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
          }
        })
        
        if (!response.ok) {
          throw new Error('Failed to fetch user')
        }
        
        const data = await response.json()
        setUser(data.data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchUser()
  }, [])

  return { user, loading, error }
}

// components/UserProfile.jsx
import { useCurrentUser } from '../hooks/useCurrentUser'

export function UserProfile() {
  const { user, loading, error } = useCurrentUser()

  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error}</div>
  if (!user) return <div>No user data</div>

  return (
    <div className="user-profile">
      <img src={user.picture} alt="Profile" />
      <h1>{user.name}</h1>
      <p>{user.email}</p>
      
      <div className="account-summary">
        <h3>Account Summary</h3>
        <p>Total Accounts: {user.account_summary.total_accounts}</p>
        <p>Active Accounts: {user.account_summary.active_accounts}</p>
        {user.account_summary.expired_tokens > 0 && (
          <p className="warning">
            Expired Tokens: {user.account_summary.expired_tokens}
          </p>
        )}
      </div>

      <div className="google-accounts">
        <h3>Primary Account</h3>
        <AccountCard account={user.primary_account} />
        
        {user.secondary_accounts.length > 0 && (
          <>
            <h3>Secondary Accounts</h3>
            {user.secondary_accounts.map(account => (
              <AccountCard key={account.id} account={account} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
```

### Next.js API Route Example
```javascript
// pages/api/user/profile.js
export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    // Get user from session (NextAuth.js)
    const session = await getSession({ req })
    if (!session?.user?.id) {
      return res.status(401).json({ error: 'Unauthorized' })
    }

    // Fetch user profile from backend
    const response = await fetch(`${process.env.API_URL}/api/v1/users/me?user_id=${session.user.id}`)
    const data = await response.json()

    if (!response.ok) {
      return res.status(response.status).json(data)
    }

    res.status(200).json(data)
  } catch (error) {
    res.status(500).json({ error: 'Internal server error' })
  }
}
```

## Rate Limits
- **Get Current User**: 60 requests per minute per user
- **Get User by ID**: 10 requests per minute per IP (admin endpoint)

## Authentication & Authorization

### Development
Currently uses query parameter `user_id` for testing purposes.

### Production (TODO)
- **Authentication**: JWT tokens or session-based auth
- **Authorization**: User can only access their own profile, admins can access any profile
- **Headers**: `Authorization: Bearer <token>`

## Pagination
The `/users/me` endpoint does not require pagination as it returns a single user. Future endpoints like `/users` (list all users) will include pagination.

## Caching
- User profiles are cached for 5 minutes
- Account summary is cached for 1 minute
- ETags supported for conditional requests

## Webhook Events
When user profiles are updated, the following webhook events are triggered:
- `user.profile.updated`
- `user.account.linked`
- `user.account.unlinked`