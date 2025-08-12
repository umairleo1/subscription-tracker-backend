# Getting Started Guide

Welcome to the Subscription Tracker API! This guide will help you get up and running quickly with our multi-account Google OAuth subscription tracking system.

## 🎯 Overview

The Subscription Tracker API is designed to work with NextAuth.js frontends to provide:
- Multi-account Google OAuth authentication
- Subscription tracking across multiple email accounts
- Professional error handling and validation
- Rate limiting and security features

## 🚀 Quick Start

### 1. Prerequisites

Before you begin, ensure you have:
- Node.js 18+ or Python 3.9+ environment
- Google Cloud Console project with OAuth 2.0 credentials
- NextAuth.js configured frontend (optional but recommended)

### 2. API Base URL

**Development:** `http://localhost:8000/api/v1`
**Production:** `https://your-api-domain.com/api/v1`

### 3. Your First API Call

Let's start by creating a user from Google OAuth data:

```bash
curl -X POST http://localhost:8000/api/v1/auth/save-user \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "123456789012345678901",
      "email": "your-email@gmail.com",
      "name": "Your Name",
      "image": "https://lh3.googleusercontent.com/a/example"
    },
    "tokens": {
      "access_token": "ya29.a0ARrdaM_example_token",
      "refresh_token": "1//0GWIt_example_refresh",
      "expires_at": 1691234567
    },
    "is_primary": true
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "New user created and Google account linked successfully",
  "data": {
    "user": {
      "id": 1,
      "email": "your-email@gmail.com",
      "name": "Your Name",
      "total_accounts": 1
    },
    "account_created": true,
    "is_new_user": true
  }
}
```

### 4. Retrieve User Profile

Now fetch the user profile you just created:

```bash
curl -X GET "http://localhost:8000/api/v1/users/me?user_id=1" \
  -H "Accept: application/json"
```

## 🔑 Authentication Flow

### Standard OAuth Flow with NextAuth.js

1. **Frontend Setup** (NextAuth.js):
```javascript
// pages/api/auth/[...nextauth].js
import NextAuth from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'

export default NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      authorization: {
        params: {
          scope: "openid email profile https://www.googleapis.com/auth/gmail.readonly"
        }
      }
    })
  ],
  callbacks: {
    async signIn({ user, account, profile }) {
      // Send OAuth data to your backend
      const response = await fetch('http://localhost:8000/api/v1/auth/save-user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile: {
            id: profile.sub,
            email: profile.email,
            name: profile.name,
            image: profile.picture
          },
          tokens: {
            access_token: account.access_token,
            refresh_token: account.refresh_token,
            expires_at: account.expires_at
          }
        })
      })
      
      return response.ok
    }
  }
})
```

2. **Backend Processing**: 
   - Receives OAuth data from NextAuth.js
   - Creates or updates user profile
   - Links multiple Google accounts
   - Returns comprehensive user data

## 📊 Core Concepts

### Users and Accounts

- **User**: A person using your application
- **Primary Account**: The main Google account (email becomes user's primary email)
- **Secondary Accounts**: Additional Google accounts linked to the same user
- **Account Limits**: Maximum 5 Google accounts per user (configurable)

### Account Linking Rules

1. **New User**: First OAuth login creates a new user with primary account
2. **Existing User (Same Email)**: Links as secondary account if `is_primary: false`
3. **Existing Account**: Updates tokens and profile information
4. **Primary Conflict**: Cannot create multiple primary accounts with same email

## 🔗 Common Integration Patterns

### 1. Simple User Creation
```javascript
async function createUser(oauthData) {
  const response = await fetch('/api/v1/auth/save-user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      profile: oauthData.profile,
      tokens: oauthData.tokens,
      is_primary: true
    })
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.message)
  }
  
  return response.json()
}
```

### 2. Account Linking
```javascript
async function linkSecondaryAccount(oauthData, existingUserEmail) {
  return createUser({
    profile: { ...oauthData.profile, email: existingUserEmail },
    tokens: oauthData.tokens,
    is_primary: false
  })
}
```

### 3. User Profile Management
```javascript
async function getUserProfile(userId) {
  const response = await fetch(`/api/v1/users/me?user_id=${userId}`)
  
  if (!response.ok) {
    throw new Error('Failed to fetch user profile')
  }
  
  const data = await response.json()
  return data.data // User profile with all accounts
}
```

### 4. Account Removal
```javascript
async function unlinkAccount(accountId) {
  const response = await fetch(`/api/v1/auth/accounts/${accountId}`, {
    method: 'DELETE'
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.message)
  }
  
  return response.json()
}
```

## 🛡️ Error Handling

### Standard Error Response Format
```json
{
  "status": "error",
  "message": "Human-readable error message",
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Detailed error message",
    "details": {},
    "validation_errors": []
  },
  "timestamp": "2025-08-08T15:25:44.000Z",
  "request_id": "uuid-here"
}
```

### Common Error Codes
- `VALIDATION_ERROR` (400): Invalid request data
- `RESOURCE_NOT_FOUND` (404): Resource doesn't exist
- `RESOURCE_CONFLICT` (409): Conflicting resource state
- `QUOTA_EXCEEDED` (429): Rate limit or account limit exceeded
- `INTERNAL_SERVER_ERROR` (500): Unexpected server error

### Error Handling Example
```javascript
async function handleApiCall() {
  try {
    const response = await fetch('/api/v1/auth/save-user', { /* ... */ })
    const data = await response.json()
    
    if (!response.ok) {
      // Handle specific error codes
      switch (data.error.code) {
        case 'VALIDATION_ERROR':
          console.error('Validation errors:', data.error.validation_errors)
          break
        case 'QUOTA_EXCEEDED':
          console.error('Account limit reached:', data.error.details)
          break
        default:
          console.error('API error:', data.message)
      }
      return
    }
    
    // Success
    console.log('User created:', data.data.user)
  } catch (error) {
    console.error('Network error:', error.message)
  }
}
```

## 🚦 Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /auth/save-user` | 10 requests | per minute |
| `DELETE /auth/accounts/{id}` | 5 requests | per minute |
| `GET /users/me` | 60 requests | per minute |
| `GET /users/{id}` | 10 requests | per minute |

### Rate Limit Headers
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1691234567
Retry-After: 30
```

## 🔍 Testing Your Integration

### 1. Test User Creation
```bash
# Test valid user creation
curl -X POST http://localhost:8000/api/v1/auth/save-user \
  -H "Content-Type: application/json" \
  -d '{"profile":{"id":"123","email":"test@gmail.com"},"tokens":{"access_token":"token"}}'

# Expected: 201 status, user created
```

### 2. Test Validation Errors
```bash
# Test missing required fields
curl -X POST http://localhost:8000/api/v1/auth/save-user \
  -H "Content-Type: application/json" \
  -d '{}'

# Expected: 422 status, validation errors
```

### 3. Test Rate Limiting
```bash
# Make multiple requests quickly
for i in {1..15}; do
  curl -X GET "http://localhost:8000/api/v1/users/me?user_id=1"
done

# Expected: 429 status after limit exceeded
```

## 📚 Next Steps

1. **Read the API Reference**: Explore detailed endpoint documentation
   - [Authentication API](../api/v1/authentication.md)
   - [Users API](../api/v1/users.md)

2. **Check Integration Guides**:
   - [NextAuth.js Integration](nextauth-integration.md)
   - [Error Handling Guide](error-handling.md)
   - [Security Best Practices](security.md)

3. **Explore Examples**:
   - [Complete API Examples](../examples/api-examples.md)
   - [Frontend Integration Examples](../examples/frontend-integration.md)

4. **Interactive Documentation**:
   - Swagger UI: http://localhost:8000/api/docs
   - ReDoc: http://localhost:8000/api/redoc

## 💡 Tips for Success

1. **Always Handle Errors**: Implement comprehensive error handling for all API calls
2. **Respect Rate Limits**: Implement backoff strategies for rate-limited requests
3. **Validate Input**: Validate data on the frontend before sending to API
4. **Use HTTPS**: Always use HTTPS in production environments
5. **Monitor Tokens**: Check token expiration and refresh when needed
6. **Log Request IDs**: Use the `request_id` from responses for debugging

## 🆘 Getting Help

- **Documentation**: Start with this guide and API reference
- **Interactive Testing**: Use Swagger UI at `/api/docs`
- **Examples**: Check the examples directory for complete implementations
- **Issues**: Report bugs or request features via GitHub issues
- **Support**: Contact api-support@yourcompany.com for assistance

Happy coding! 🎉