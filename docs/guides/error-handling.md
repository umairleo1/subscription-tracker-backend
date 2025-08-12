# Error Handling Guide

This guide covers comprehensive error handling for the Subscription Tracker API, including error formats, common scenarios, and best practices for robust integration.

## 🏗️ Error Response Structure

All API errors follow a consistent structure for predictable handling:

```json
{
  "status": "error",
  "message": "Human-readable error summary",
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Detailed technical error message",
    "details": {
      "field": "additional context"
    },
    "validation_errors": [
      {
        "field": "profile.email",
        "message": "field required",
        "type": "value_error.missing",
        "input": null
      }
    ]
  },
  "meta": null,
  "pagination": null,
  "timestamp": "2025-08-08T15:25:44.000Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Field Descriptions

- **status**: Always `"error"` for error responses
- **message**: User-friendly error message for display
- **data**: Always `null` for error responses
- **error.code**: Machine-readable error code for programmatic handling
- **error.message**: Detailed technical error description
- **error.details**: Additional context specific to the error
- **error.validation_errors**: Array of field validation errors (when applicable)
- **request_id**: Unique identifier for tracing and debugging

## 📋 Error Codes Reference

### Client Errors (4xx)

#### VALIDATION_ERROR (400)
Request data validation failed.

**Common Causes:**
- Missing required fields
- Invalid field formats
- Type mismatches
- Constraint violations

**Example:**
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
      },
      {
        "field": "tokens.access_token",
        "message": "ensure this value has at least 10 characters",
        "type": "value_error.any_str.min_length",
        "input": "short"
      }
    ]
  }
}
```

#### RESOURCE_NOT_FOUND (404)
Requested resource doesn't exist.

**Example:**
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

#### RESOURCE_CONFLICT (409)
Request conflicts with current resource state.

**Example:**
```json
{
  "status": "error",
  "message": "User with email user@gmail.com already exists. Cannot create another primary account.",
  "error": {
    "code": "RESOURCE_CONFLICT",
    "details": {
      "conflicting_field": "email",
      "conflicting_value": "user@gmail.com"
    }
  }
}
```

#### QUOTA_EXCEEDED (429)
Rate limit or account limit exceeded.

**Example:**
```json
{
  "status": "error",
  "message": "Maximum number of Google accounts (5) reached",
  "error": {
    "code": "QUOTA_EXCEEDED",
    "details": {
      "current_count": 5,
      "max_allowed": 5,
      "quota_type": "google_accounts_per_user"
    }
  }
}
```

#### FORBIDDEN (403)
Access denied for the requested resource.

**Example:**
```json
{
  "status": "error",
  "message": "Cannot unlink primary Google account. Primary account is required to maintain user identity.",
  "error": {
    "code": "FORBIDDEN",
    "details": {
      "reason": "primary_account_protection"
    }
  }
}
```

### Server Errors (5xx)

#### INTERNAL_SERVER_ERROR (500)
Unexpected server error occurred.

**Example:**
```json
{
  "status": "error",
  "message": "An unexpected error occurred",
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "details": {
      "error": "Database connection failed"
    }
  }
}
```

#### DATABASE_ERROR (500)
Database operation failed.

**Example:**
```json
{
  "status": "error",
  "message": "Failed to save user data",
  "error": {
    "code": "DATABASE_ERROR",
    "details": {
      "operation": "user_creation",
      "table": "users"
    }
  }
}
```

## 🛡️ Error Handling Strategies

### 1. Comprehensive Try-Catch

```javascript
async function saveUser(userData) {
  try {
    const response = await fetch('/api/v1/auth/save-user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData)
    })
    
    const data = await response.json()
    
    if (!response.ok) {
      throw new ApiError(data, response.status)
    }
    
    return data.data
  } catch (error) {
    if (error instanceof ApiError) {
      throw error // Re-throw API errors
    }
    
    // Handle network errors
    throw new Error('Network error occurred')
  }
}

class ApiError extends Error {
  constructor(errorResponse, statusCode) {
    super(errorResponse.message)
    this.name = 'ApiError'
    this.code = errorResponse.error.code
    this.details = errorResponse.error.details
    this.validationErrors = errorResponse.error.validation_errors
    this.statusCode = statusCode
    this.requestId = errorResponse.request_id
  }
}
```

### 2. Error Code Specific Handling

```javascript
async function handleUserCreation(userData) {
  try {
    return await saveUser(userData)
  } catch (error) {
    if (!(error instanceof ApiError)) {
      console.error('Network error:', error.message)
      return { success: false, error: 'Connection failed' }
    }
    
    switch (error.code) {
      case 'VALIDATION_ERROR':
        return handleValidationError(error)
      case 'RESOURCE_CONFLICT':
        return handleConflictError(error)
      case 'QUOTA_EXCEEDED':
        return handleQuotaError(error)
      default:
        console.error('Unexpected API error:', error.message)
        return { success: false, error: 'An unexpected error occurred' }
    }
  }
}

function handleValidationError(error) {
  const fieldErrors = {}
  
  error.validationErrors?.forEach(validationError => {
    fieldErrors[validationError.field] = validationError.message
  })
  
  return {
    success: false,
    error: 'Please check your input',
    fieldErrors
  }
}

function handleConflictError(error) {
  if (error.details.conflicting_field === 'email') {
    return {
      success: false,
      error: 'An account with this email already exists',
      suggestion: 'Try linking this as a secondary account instead'
    }
  }
  
  return {
    success: false,
    error: error.message
  }
}

function handleQuotaError(error) {
  if (error.details.quota_type === 'google_accounts_per_user') {
    return {
      success: false,
      error: `Maximum number of accounts (${error.details.max_allowed}) reached`,
      suggestion: 'Remove an existing account before adding a new one'
    }
  }
  
  return {
    success: false,
    error: error.message
  }
}
```

### 3. Rate Limit Handling with Exponential Backoff

```javascript
async function apiCallWithRetry(apiCall, maxRetries = 3) {
  let attempt = 0
  
  while (attempt <= maxRetries) {
    try {
      return await apiCall()
    } catch (error) {
      if (!(error instanceof ApiError)) {
        throw error // Don't retry network errors
      }
      
      if (error.code === 'QUOTA_EXCEEDED' && attempt < maxRetries) {
        // Extract retry-after from response headers if available
        const retryAfter = error.retryAfter || Math.pow(2, attempt) * 1000
        
        console.log(`Rate limited. Retrying in ${retryAfter}ms...`)
        await sleep(retryAfter)
        attempt++
        continue
      }
      
      throw error // Don't retry other errors
    }
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// Usage
const result = await apiCallWithRetry(() => saveUser(userData))
```

## 🎯 Frontend Integration Patterns

### React Hook for Error Handling

```javascript
import { useState, useCallback } from 'react'

export function useApiError() {
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleApiCall = useCallback(async (apiCall) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const result = await apiCall()
      setIsLoading(false)
      return result
    } catch (error) {
      const formattedError = formatApiError(error)
      setError(formattedError)
      setIsLoading(false)
      throw formattedError
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return { error, isLoading, handleApiCall, clearError }
}

function formatApiError(error) {
  if (!(error instanceof ApiError)) {
    return {
      type: 'network',
      message: 'Connection failed. Please check your internet connection.',
      canRetry: true
    }
  }

  const formatted = {
    type: 'api',
    code: error.code,
    message: error.message,
    details: error.details,
    requestId: error.requestId,
    canRetry: false
  }

  // Customize based on error code
  switch (error.code) {
    case 'QUOTA_EXCEEDED':
      formatted.canRetry = true
      formatted.retryDelay = 60000 // 1 minute
      break
    case 'INTERNAL_SERVER_ERROR':
      formatted.canRetry = true
      formatted.retryDelay = 5000 // 5 seconds
      break
  }

  return formatted
}
```

### Error Display Component

```javascript
import React from 'react'

export function ErrorDisplay({ error, onRetry, onDismiss }) {
  if (!error) return null

  const getErrorStyle = (error) => {
    switch (error.code) {
      case 'VALIDATION_ERROR':
        return 'warning'
      case 'QUOTA_EXCEEDED':
        return 'info'
      default:
        return 'error'
    }
  }

  return (
    <div className={`error-display ${getErrorStyle(error)}`}>
      <div className="error-content">
        <h4>Error</h4>
        <p>{error.message}</p>
        
        {error.validationErrors && (
          <ul className="validation-errors">
            {error.validationErrors.map((validationError, index) => (
              <li key={index}>
                <strong>{validationError.field}:</strong> {validationError.message}
              </li>
            ))}
          </ul>
        )}
        
        {error.requestId && (
          <p className="request-id">
            Request ID: <code>{error.requestId}</code>
          </p>
        )}
      </div>
      
      <div className="error-actions">
        {error.canRetry && onRetry && (
          <button onClick={onRetry}>
            Retry
          </button>
        )}
        <button onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </div>
  )
}
```

## 🔍 Debugging and Monitoring

### Logging Errors

```javascript
function logApiError(error, context = {}) {
  const errorLog = {
    timestamp: new Date().toISOString(),
    level: 'ERROR',
    type: error instanceof ApiError ? 'api_error' : 'network_error',
    message: error.message,
    context,
    ...(error instanceof ApiError && {
      code: error.code,
      statusCode: error.statusCode,
      requestId: error.requestId,
      details: error.details
    })
  }

  // Send to logging service
  console.error('API Error:', errorLog)
  
  // Optional: Send to external logging service
  // logService.error(errorLog)
}
```

### Error Monitoring

```javascript
class ErrorMonitor {
  constructor() {
    this.errorCounts = new Map()
    this.lastErrors = []
  }

  recordError(error) {
    const key = error instanceof ApiError ? error.code : 'network_error'
    
    this.errorCounts.set(key, (this.errorCounts.get(key) || 0) + 1)
    this.lastErrors.unshift({
      error,
      timestamp: Date.now()
    })
    
    // Keep only last 50 errors
    this.lastErrors = this.lastErrors.slice(0, 50)
    
    // Alert on high error rates
    if (this.errorCounts.get(key) > 10) {
      this.alertHighErrorRate(key)
    }
  }

  alertHighErrorRate(errorType) {
    console.warn(`High error rate detected for ${errorType}`)
    // Send alert to monitoring service
  }

  getErrorStats() {
    return {
      counts: Object.fromEntries(this.errorCounts),
      recent: this.lastErrors.slice(0, 10)
    }
  }
}

const errorMonitor = new ErrorMonitor()
```

## ⚡ Performance Considerations

### Error Response Caching

```javascript
class ErrorCache {
  constructor(ttl = 60000) { // 1 minute TTL
    this.cache = new Map()
    this.ttl = ttl
  }

  shouldRetry(error, cacheKey) {
    const cached = this.cache.get(cacheKey)
    
    if (!cached) return true
    if (Date.now() - cached.timestamp > this.ttl) {
      this.cache.delete(cacheKey)
      return true
    }
    
    // Don't retry if same error occurred recently
    return cached.error.code !== error.code
  }

  cacheError(error, cacheKey) {
    this.cache.set(cacheKey, {
      error,
      timestamp: Date.now()
    })
  }
}
```

## 📚 Best Practices

### 1. Always Handle Errors
Never ignore API errors. Always implement appropriate error handling.

### 2. Provide User-Friendly Messages
Convert technical error messages into user-friendly language:

```javascript
function getUserFriendlyMessage(error) {
  const messages = {
    'VALIDATION_ERROR': 'Please check your input and try again.',
    'RESOURCE_NOT_FOUND': 'The requested information was not found.',
    'QUOTA_EXCEEDED': 'You have reached the maximum limit. Please try again later.',
    'FORBIDDEN': 'You do not have permission to perform this action.',
    'INTERNAL_SERVER_ERROR': 'Something went wrong on our end. Please try again.'
  }
  
  return messages[error.code] || 'An unexpected error occurred.'
}
```

### 3. Use Request IDs for Support
Always include the `request_id` when reporting issues:

```javascript
function generateSupportInfo(error) {
  return {
    requestId: error.requestId,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href
  }
}
```

### 4. Implement Graceful Degradation
Provide fallback functionality when APIs fail:

```javascript
async function getUserWithFallback(userId) {
  try {
    return await getUser(userId)
  } catch (error) {
    // Return cached data or minimal user object
    return getCachedUser(userId) || { id: userId, name: 'Unknown User' }
  }
}
```

### 5. Monitor Error Patterns
Track error patterns to identify systemic issues:

```javascript
// Track errors by endpoint
const errorsByEndpoint = {}

function trackError(endpoint, error) {
  if (!errorsByEndpoint[endpoint]) {
    errorsByEndpoint[endpoint] = []
  }
  
  errorsByEndpoint[endpoint].push({
    code: error.code,
    timestamp: Date.now()
  })
}
```

## 🚨 Common Pitfalls

1. **Not Handling Network Errors**: Always account for network connectivity issues
2. **Ignoring Rate Limits**: Implement backoff strategies for rate-limited requests
3. **Poor Error Messages**: Don't show technical error messages to end users
4. **Missing Request IDs**: Always log request IDs for debugging
5. **Not Validating Input**: Validate data on frontend before sending to API
6. **Infinite Retry Loops**: Always limit retry attempts
7. **Blocking UI**: Show loading states and allow cancellation of requests

By following this error handling guide, you'll create a robust integration that gracefully handles all error scenarios and provides excellent user experience even when things go wrong.