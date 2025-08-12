# Authentication API - DEPRECATED

## ⚠️ **IMPORTANT: All auth endpoints have been REMOVED**

**All authentication functionality has been consolidated into the User Management API under `/api/v1/users/` endpoints.**

**This documentation is kept for reference only. Please use the new endpoints:**

- **OLD**: `POST /api/v1/auth/save-user` 
- **NEW**: `POST /api/v1/users/` ✅

- **OLD**: `DELETE /api/v1/auth/accounts/{account_id}` 
- **NEW**: `DELETE /api/v1/users/{user_id}/linked-accounts/{account_id}` ✅

## 🚀 **Use the New User Management API**

Please refer to the updated documentation:

- **[Complete API Guide](comprehensive-api-guide.md)** - Enterprise-grade documentation
- **[User Management API](users.md)** - Detailed user endpoints documentation
- **[README.md](../../../README.md)** - Quick start and examples

---

## Legacy Documentation (For Reference Only)

## Endpoints

### Save User from OAuth
Save or update user data received from Google OAuth authentication via NextAuth.js.

**Endpoint:** `POST /auth/save-user`

**Description:** 
This endpoint receives Google OAuth profile and tokens from the NextAuth.js frontend and handles both new user creation and linking additional Google accounts to existing users.

**Request Body:**
```json
{
  "profile": {
    "id": "string",           // Required: Google user ID
    "email": "string",        // Required: Google email address  
    "name": "string",         // Optional: Full name from Google
    "image": "string"         // Optional: Profile picture URL
  },
  "tokens": {
    "access_token": "string",     // Required: Google access token
    "refresh_token": "string",    // Optional: Google refresh token
    "id_token": "string",         // Optional: Google ID token
    "expires_at": 1691234567,     // Optional: Token expiration timestamp
    "token_type": "Bearer",       // Optional: Token type (default: "Bearer")
    "scope": "string"             // Optional: Granted OAuth scopes
  },
  "is_primary": true              // Optional: Whether this is primary account (default: true)
}
```

**Response (201 - New User Created):**
```json
{
  "status": "success",
  "message": "New user created and Google account linked successfully",
  "data": {
    "user": {
      "id": 1,
      "email": "user@gmail.com",
      "name": "John Doe",
      "picture": "https://lh3.googleusercontent.com/a/example",
      "is_active": true,
      "created_at": "2025-08-08T13:48:49.000Z",
      "updated_at": null,
      "last_login_at": "2025-08-08T13:48:49.000Z",
      "primary_account": {
        "id": 1,
        "google_id": "123456789012345678901",
        "email": "user@gmail.com",
        "name": "John Doe",
        "picture": "https://lh3.googleusercontent.com/a/example",
        "is_primary": true,
        "is_active": true,
        "created_at": "2025-08-08T13:48:49.000Z",
        "updated_at": null,
        "last_login_at": "2025-08-08T13:48:49.000Z",
        "scope": "openid email profile",
        "token_expires_at": "2025-08-08T14:48:49.000Z",
        "is_token_expired": false
      },
      "secondary_accounts": [],
      "total_accounts": 1
    },
    "account_created": true,
    "is_new_user": true
  },
  "error": null,
  "meta": null,
  "pagination": null,
  "timestamp": "2025-08-08T13:48:49.000Z",
  "request_id": "uuid-here"
}
```

**Response (200 - Account Linked):**
```json
{
  "status": "success", 
  "message": "Additional Google account linked successfully",
  "data": {
    "user": {
      // Same user structure as above
    },
    "account_created": true,
    "is_new_user": false
  }
}
```

**Response (200 - Profile Updated):**
```json
{
  "status": "success",
  "message": "User profile and tokens updated successfully", 
  "data": {
    "user": {
      // Same user structure as above
    },
    "account_created": false,
    "is_new_user": false
  }
}
```

**Business Rules:**
- If Google account doesn't exist: Creates new user or links to existing user by email
- If Google account exists: Updates tokens and profile information
- Primary account uniqueness: Only one primary account per email address
- Account limits: Maximum 5 Google accounts per user (configurable)

**Error Responses:**

*400 - Validation Error:*
```json
{
  "status": "error",
  "message": "Request validation failed",
  "error": {
    "code": "VALIDATION_ERROR",
    "validation_errors": [
      {
        "field": "profile.email",
        "message": "field required",
        "type": "value_error.missing"
      }
    ]
  }
}
```

*409 - Resource Conflict:*
```json
{
  "status": "error",
  "message": "User with email user@gmail.com already exists. Cannot create another primary account.",
  "error": {
    "code": "RESOURCE_CONFLICT",
    "details": {}
  }
}
```

*429 - Rate Limit Exceeded:*
```json
{
  "status": "error", 
  "message": "Maximum number of Google accounts (5) reached",
  "error": {
    "code": "QUOTA_EXCEEDED",
    "details": {
      "current_count": 5,
      "max_allowed": 5
    }
  }
}
```

### Unlink Google Account
Remove a secondary Google account from a user's profile.

**Endpoint:** `DELETE /auth/accounts/{account_id}`

**Description:**
Removes a secondary Google account. Primary accounts cannot be unlinked to maintain user identity and system integrity.

**Path Parameters:**
- `account_id` (integer): ID of the Google account to unlink

**Response (200 - Success):**
```json
{
  "status": "success",
  "message": "Google account unlinked successfully",
  "data": {
    "unlinked_account": {
      "id": 2,
      "email": "secondary@gmail.com", 
      "was_primary": false
    },
    "user": {
      "id": 1,
      "email": "user@gmail.com",
      // ... complete user object with remaining accounts
      "total_accounts": 1
    }
  }
}
```

**Security Rules:**
- Cannot unlink primary Google account
- User must have at least one Google account
- Only account owner can unlink their accounts (TODO: implement authentication)

**Error Responses:**

*400 - Validation Error:*
```json
{
  "status": "error",
  "message": "Invalid account ID", 
  "error": {
    "code": "VALIDATION_ERROR"
  }
}
```

*403 - Cannot Unlink Primary:*
```json
{
  "status": "error",
  "message": "Cannot unlink primary Google account. Primary account is required to maintain user identity.",
  "error": {
    "code": "VALIDATION_ERROR"
  }
}
```

*404 - Account Not Found:*
```json
{
  "status": "error",
  "message": "Google account not found (ID: 999)",
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "details": {
      "resource": "Google account",
      "resource_id": "999"
    }
  }
}
```

## Usage Examples

### Example 1: Creating New User
```bash
curl -X POST http://localhost:8000/api/v1/auth/save-user \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "123456789012345678901",
      "email": "newuser@gmail.com", 
      "name": "New User",
      "image": "https://lh3.googleusercontent.com/a/example"
    },
    "tokens": {
      "access_token": "ya29.a0ARrdaM_example_token",
      "refresh_token": "1//0GWIt_example_refresh",
      "expires_at": 1691234567,
      "scope": "openid email profile"
    },
    "is_primary": true
  }'
```

### Example 2: Linking Secondary Account
```bash
curl -X POST http://localhost:8000/api/v1/auth/save-user \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "id": "987654321098765432109",
      "email": "existing@gmail.com",
      "name": "Existing User Secondary"
    },
    "tokens": {
      "access_token": "ya29.a0ARrdaM_secondary_token"
    },
    "is_primary": false
  }'
```

### Example 3: Unlinking Account
```bash
curl -X DELETE http://localhost:8000/api/v1/auth/accounts/2
```

## Integration with NextAuth.js

This API is designed to work seamlessly with NextAuth.js. Here's how to integrate:

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
      // Send to your backend
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

## Rate Limits
- **Save User**: 10 requests per minute per IP
- **Unlink Account**: 5 requests per minute per IP

## Security Considerations
- All tokens are stored securely (consider encryption in production)
- Rate limiting prevents abuse
- Input validation prevents malicious data
- CORS configured for specific origins only