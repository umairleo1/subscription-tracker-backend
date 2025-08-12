# Complete API Examples

This document provides comprehensive, real-world examples of using the Subscription Tracker API for common integration scenarios.

## 🔧 Setup

### Base Configuration
```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1'

// Helper function for API calls
async function apiCall(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  }

  const response = await fetch(url, config)
  const data = await response.json()

  if (!response.ok) {
    throw new ApiError(data, response.status)
  }

  return data
}

class ApiError extends Error {
  constructor(errorResponse, statusCode) {
    super(errorResponse.message)
    this.code = errorResponse.error.code
    this.statusCode = statusCode
    this.details = errorResponse.error.details
    this.requestId = errorResponse.request_id
  }
}
```

## 👤 User Management Examples

### Example 1: Complete User Registration Flow

```javascript
/**
 * Complete user registration from Google OAuth
 * Handles new user creation with comprehensive error handling
 */
async function registerUser(googleOAuthData) {
  console.log('🚀 Starting user registration...')
  
  const userData = {
    profile: {
      id: googleOAuthData.sub,
      email: googleOAuthData.email,
      name: googleOAuthData.name,
      image: googleOAuthData.picture
    },
    tokens: {
      access_token: googleOAuthData.access_token,
      refresh_token: googleOAuthData.refresh_token,
      expires_at: googleOAuthData.expires_at,
      scope: googleOAuthData.scope
    },
    is_primary: true
  }

  try {
    const response = await apiCall('/auth/save-user', {
      method: 'POST',
      body: JSON.stringify(userData)
    })

    console.log('✅ User registered successfully')
    console.log(`User ID: ${response.data.user.id}`)
    console.log(`Email: ${response.data.user.email}`)
    console.log(`New User: ${response.data.is_new_user}`)
    
    return {
      success: true,
      user: response.data.user,
      isNewUser: response.data.is_new_user
    }
  } catch (error) {
    console.error('❌ Registration failed:', error.message)
    
    if (error.code === 'RESOURCE_CONFLICT') {
      console.log('💡 User already exists - this might be a secondary account linking')
      return {
        success: false,
        error: 'User with this email already exists',
        suggestion: 'Try linking as secondary account'
      }
    }
    
    return {
      success: false,
      error: error.message
    }
  }
}

// Usage
const googleData = {
  sub: '123456789012345678901',
  email: 'john.doe@gmail.com',
  name: 'John Doe',
  picture: 'https://lh3.googleusercontent.com/a/example',
  access_token: 'ya29.a0ARrdaM...',
  refresh_token: '1//0GWIt...',
  expires_at: 1691234567,
  scope: 'openid email profile'
}

const result = await registerUser(googleData)
console.log('Registration result:', result)
```

### Example 2: Multi-Account Management

```javascript
/**
 * Complete multi-account management system
 * Handles linking, unlinking, and managing multiple Google accounts
 */
class MultiAccountManager {
  constructor(userId) {
    this.userId = userId
  }

  async getUserProfile() {
    try {
      const response = await apiCall(`/users/me?user_id=${this.userId}`)
      return response.data
    } catch (error) {
      console.error('Failed to fetch user profile:', error.message)
      throw error
    }
  }

  async linkSecondaryAccount(googleOAuthData, primaryUserEmail) {
    console.log('🔗 Linking secondary account...')
    
    const userData = {
      profile: {
        id: googleOAuthData.sub,
        email: primaryUserEmail, // Use primary user's email for linking
        name: googleOAuthData.name,
        image: googleOAuthData.picture
      },
      tokens: {
        access_token: googleOAuthData.access_token,
        refresh_token: googleOAuthData.refresh_token,
        expires_at: googleOAuthData.expires_at
      },
      is_primary: false // Important: This is a secondary account
    }

    try {
      const response = await apiCall('/auth/save-user', {
        method: 'POST',
        body: JSON.stringify(userData)
      })

      console.log('✅ Secondary account linked successfully')
      return {
        success: true,
        user: response.data.user,
        accountLinked: response.data.account_created
      }
    } catch (error) {
      console.error('❌ Failed to link secondary account:', error.message)
      
      if (error.code === 'QUOTA_EXCEEDED') {
        return {
          success: false,
          error: `Maximum accounts limit reached (${error.details.max_allowed})`,
          currentCount: error.details.current_count
        }
      }
      
      throw error
    }
  }

  async unlinkAccount(accountId) {
    console.log(`🔓 Unlinking account ${accountId}...`)
    
    try {
      const response = await apiCall(`/auth/accounts/${accountId}`, {
        method: 'DELETE'
      })

      console.log('✅ Account unlinked successfully')
      console.log('Unlinked account:', response.data.unlinked_account)
      
      return {
        success: true,
        unlinkedAccount: response.data.unlinked_account,
        updatedUser: response.data.user
      }
    } catch (error) {
      console.error('❌ Failed to unlink account:', error.message)
      
      if (error.code === 'VALIDATION_ERROR') {
        return {
          success: false,
          error: 'Cannot unlink primary account or last remaining account'
        }
      }
      
      throw error
    }
  }

  async getAccountSummary() {
    const user = await this.getUserProfile()
    
    const summary = {
      userId: user.id,
      primaryEmail: user.email,
      totalAccounts: user.total_accounts,
      accounts: {
        primary: user.primary_account,
        secondary: user.secondary_accounts
      },
      healthCheck: {
        hasValidPrimary: !!user.primary_account,
        expiredTokens: user.account_summary.expired_tokens,
        allAccountsActive: user.account_summary.active_accounts === user.total_accounts
      }
    }
    
    console.log('📊 Account Summary:', summary)
    return summary
  }

  async refreshExpiredTokens() {
    const user = await this.getUserProfile()
    const expiredAccounts = []
    
    // Check primary account
    if (user.primary_account?.is_token_expired) {
      expiredAccounts.push({
        id: user.primary_account.id,
        email: user.primary_account.email,
        type: 'primary'
      })
    }
    
    // Check secondary accounts
    user.secondary_accounts?.forEach(account => {
      if (account.is_token_expired) {
        expiredAccounts.push({
          id: account.id,
          email: account.email,
          type: 'secondary'
        })
      }
    })
    
    if (expiredAccounts.length === 0) {
      console.log('✅ All tokens are valid')
      return { success: true, message: 'No tokens need refreshing' }
    }
    
    console.log(`⚠️  Found ${expiredAccounts.length} expired tokens:`)
    expiredAccounts.forEach(account => {
      console.log(`   - ${account.email} (${account.type})`)
    })
    
    return {
      success: false,
      expiredAccounts,
      message: 'Token refresh required - redirect user to re-authenticate'
    }
  }
}

// Usage Example
async function demonstrateMultiAccountManagement() {
  console.log('🎭 Multi-Account Management Demo')
  console.log('=' .repeat(40))
  
  const manager = new MultiAccountManager(1)
  
  // Get current profile
  const profile = await manager.getAccountSummary()
  
  // Link a secondary account
  const secondaryAccountData = {
    sub: '987654321098765432109',
    email: 'john.work@gmail.com',
    name: 'John Doe (Work)',
    access_token: 'ya29.a0ARrdaM_work_token',
    expires_at: Date.now() / 1000 + 3600
  }
  
  const linkResult = await manager.linkSecondaryAccount(
    secondaryAccountData,
    profile.primaryEmail
  )
  
  if (linkResult.success) {
    console.log('🎉 Secondary account linked!')
    
    // Get updated summary
    await manager.getAccountSummary()
    
    // Check for expired tokens
    await manager.refreshExpiredTokens()
  }
}
```

### Example 3: Error Handling Showcase

```javascript
/**
 * Comprehensive error handling examples
 * Demonstrates handling all possible API error scenarios
 */
class ErrorHandlingShowcase {
  async demonstrateValidationErrors() {
    console.log('🔍 Testing validation error handling...')
    
    // Test missing required fields
    try {
      await apiCall('/auth/save-user', {
        method: 'POST',
        body: JSON.stringify({
          profile: {
            // Missing required 'id' and 'email'
            name: 'Test User'
          },
          tokens: {
            // Missing required 'access_token'
          }
        })
      })
    } catch (error) {
      console.log('✅ Validation error handled correctly:')
      console.log(`   Code: ${error.code}`)
      console.log(`   Status: ${error.statusCode}`)
      
      if (error.details.validation_errors) {
        console.log('   Validation errors:')
        error.details.validation_errors.forEach(err => {
          console.log(`     - ${err.field}: ${err.message}`)
        })
      }
    }
  }

  async demonstrateResourceConflict() {
    console.log('🔍 Testing resource conflict handling...')
    
    // First create a user
    const userData = {
      profile: {
        id: '123456789',
        email: 'conflict@example.com',
        name: 'Conflict User'
      },
      tokens: {
        access_token: 'valid_token'
      },
      is_primary: true
    }
    
    try {
      await apiCall('/auth/save-user', {
        method: 'POST',
        body: JSON.stringify(userData)
      })
      console.log('✅ First user created')
      
      // Try to create another primary account with same email
      await apiCall('/auth/save-user', {
        method: 'POST',
        body: JSON.stringify({
          ...userData,
          profile: { ...userData.profile, id: '987654321' } // Different Google ID
        })
      })
    } catch (error) {
      if (error.code === 'RESOURCE_CONFLICT') {
        console.log('✅ Resource conflict handled correctly:')
        console.log(`   Message: ${error.message}`)
        console.log('   Suggestion: Link as secondary account instead')
      }
    }
  }

  async demonstrateQuotaExceeded() {
    console.log('🔍 Testing quota exceeded handling...')
    
    // This would typically happen after linking multiple accounts
    try {
      // Simulate linking 6th account (over the 5 account limit)
      await apiCall('/auth/save-user', {
        method: 'POST',
        body: JSON.stringify({
          profile: {
            id: '999999999',
            email: 'existing@example.com', // Existing user email
            name: 'Sixth Account'
          },
          tokens: {
            access_token: 'token'
          },
          is_primary: false
        })
      })
    } catch (error) {
      if (error.code === 'QUOTA_EXCEEDED') {
        console.log('✅ Quota exceeded handled correctly:')
        console.log(`   Current: ${error.details.current_count}`)
        console.log(`   Maximum: ${error.details.max_allowed}`)
        console.log('   Action: Remove an account before adding new one')
      }
    }
  }

  async demonstrateResourceNotFound() {
    console.log('🔍 Testing resource not found handling...')
    
    try {
      await apiCall('/users/me?user_id=999999')
    } catch (error) {
      if (error.code === 'RESOURCE_NOT_FOUND') {
        console.log('✅ Resource not found handled correctly:')
        console.log(`   Resource: ${error.details.resource}`)
        console.log(`   ID: ${error.details.resource_id}`)
      }
    }
  }

  async demonstrateRateLimiting() {
    console.log('🔍 Testing rate limiting...')
    
    const requests = []
    
    // Fire 15 rapid requests (over the 10/minute limit)
    for (let i = 0; i < 15; i++) {
      requests.push(
        apiCall('/users/me?user_id=1').catch(error => ({
          error: true,
          code: error.code,
          attempt: i + 1
        }))
      )
    }
    
    const results = await Promise.all(requests)
    
    const rateLimited = results.filter(r => r.error && r.code === 'QUOTA_EXCEEDED')
    
    console.log(`✅ Rate limiting test complete:`)
    console.log(`   Successful requests: ${results.length - rateLimited.length}`)
    console.log(`   Rate limited requests: ${rateLimited.length}`)
    
    if (rateLimited.length > 0) {
      console.log(`   First rate limit at attempt: ${rateLimited[0].attempt}`)
    }
  }

  async runAllTests() {
    console.log('🧪 Error Handling Comprehensive Test Suite')
    console.log('=' .repeat(50))
    
    await this.demonstrateValidationErrors()
    console.log()
    
    await this.demonstrateResourceConflict()
    console.log()
    
    await this.demonstrateQuotaExceeded()
    console.log()
    
    await this.demonstrateResourceNotFound()
    console.log()
    
    await this.demonstrateRateLimiting()
    console.log()
    
    console.log('🎉 All error handling tests completed!')
  }
}

// Run the showcase
const errorShowcase = new ErrorHandlingShowcase()
await errorShowcase.runAllTests()
```

## 🚀 Production Integration Examples

### Example 4: NextAuth.js Complete Integration

```javascript
// pages/api/auth/[...nextauth].js
import NextAuth from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'

// API client for backend communication
class BackendAPIClient {
  constructor() {
    this.baseURL = process.env.BACKEND_API_URL || 'http://localhost:8000/api/v1'
  }

  async saveUser(profile, tokens, isPrimary = true) {
    const response = await fetch(`${this.baseURL}/auth/save-user`, {
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
          access_token: tokens.access_token,
          refresh_token: tokens.refresh_token,
          expires_at: tokens.expires_at,
          scope: tokens.scope
        },
        is_primary: isPrimary
      })
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(`Backend API Error: ${error.message}`)
    }

    return response.json()
  }

  async getUser(userId) {
    const response = await fetch(`${this.baseURL}/users/me?user_id=${userId}`)
    
    if (!response.ok) {
      if (response.status === 404) {
        return null // User not found
      }
      const error = await response.json()
      throw new Error(`Backend API Error: ${error.message}`)
    }

    const data = await response.json()
    return data.data
  }
}

const backendAPI = new BackendAPIClient()

export default NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      authorization: {
        params: {
          scope: [
            'openid',
            'email',
            'profile',
            'https://www.googleapis.com/auth/gmail.readonly'
          ].join(' ')
        }
      }
    })
  ],
  
  callbacks: {
    async signIn({ user, account, profile }) {
      try {
        console.log('🔐 Processing sign-in for:', profile.email)
        
        // Save/update user in backend
        const result = await backendAPI.saveUser(profile, account, true)
        
        // Store backend user ID in the session
        user.backendId = result.data.user.id
        user.isNewUser = result.data.is_new_user
        user.accountsCount = result.data.user.total_accounts
        
        console.log(`✅ User processed successfully - Backend ID: ${user.backendId}`)
        return true
      } catch (error) {
        console.error('❌ Sign-in failed:', error.message)
        
        // Allow sign-in to continue but log the error
        // In production, you might want to fail the sign-in
        return true
      }
    },

    async jwt({ token, user, account }) {
      // Persist backend user ID in JWT
      if (user) {
        token.backendId = user.backendId
        token.isNewUser = user.isNewUser
        token.accountsCount = user.accountsCount
      }

      // Refresh user data periodically
      if (token.backendId && Date.now() > (token.lastSync || 0) + 60000) {
        try {
          const userData = await backendAPI.getUser(token.backendId)
          if (userData) {
            token.accountsCount = userData.total_accounts
            token.hasExpiredTokens = userData.account_summary.expired_tokens > 0
            token.lastSync = Date.now()
          }
        } catch (error) {
          console.error('Failed to sync user data:', error.message)
        }
      }

      return token
    },

    async session({ session, token }) {
      // Include backend data in session
      session.user.backendId = token.backendId
      session.user.isNewUser = token.isNewUser
      session.user.accountsCount = token.accountsCount
      session.user.hasExpiredTokens = token.hasExpiredTokens
      
      return session
    }
  },

  events: {
    async signIn({ user, account, profile, isNewUser }) {
      console.log(`📊 Sign-in event: ${profile.email} (New: ${isNewUser})`)
    },
    
    async signOut({ token }) {
      console.log(`👋 Sign-out event: Backend ID ${token.backendId}`)
    }
  }
})
```

### Example 5: React Application Integration

```javascript
// hooks/useBackendUser.js
import { useSession } from 'next-auth/react'
import { useState, useEffect } from 'react'

export function useBackendUser() {
  const { data: session, status } = useSession()
  const [backendUser, setBackendUser] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchBackendUser() {
      if (status !== 'authenticated' || !session?.user?.backendId) {
        return
      }

      setLoading(true)
      setError(null)

      try {
        const response = await fetch(`/api/backend/user/${session.user.backendId}`)
        
        if (!response.ok) {
          throw new Error('Failed to fetch user data')
        }

        const userData = await response.json()
        setBackendUser(userData)
      } catch (err) {
        setError(err.message)
        console.error('Failed to fetch backend user:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchBackendUser()
  }, [session, status])

  const linkSecondaryAccount = async (googleAccount) => {
    if (!session?.user?.email) {
      throw new Error('No primary user session')
    }

    const response = await fetch('/api/backend/auth/save-user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: {
          id: googleAccount.sub,
          email: session.user.email, // Use primary user's email
          name: googleAccount.name,
          image: googleAccount.picture
        },
        tokens: {
          access_token: googleAccount.access_token,
          refresh_token: googleAccount.refresh_token
        },
        is_primary: false
      })
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.message)
    }

    const result = await response.json()
    
    // Refresh backend user data
    setBackendUser(result.data.user)
    
    return result
  }

  const unlinkAccount = async (accountId) => {
    const response = await fetch(`/api/backend/auth/accounts/${accountId}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.message)
    }

    const result = await response.json()
    
    // Refresh backend user data
    setBackendUser(result.data.user)
    
    return result
  }

  return {
    backendUser,
    loading,
    error,
    linkSecondaryAccount,
    unlinkAccount,
    refresh: () => fetchBackendUser()
  }
}

// components/AccountManager.jsx
import React from 'react'
import { useBackendUser } from '../hooks/useBackendUser'

export function AccountManager() {
  const { 
    backendUser, 
    loading, 
    error, 
    linkSecondaryAccount, 
    unlinkAccount 
  } = useBackendUser()

  if (loading) return <div>Loading account information...</div>
  if (error) return <div>Error: {error}</div>
  if (!backendUser) return <div>No account data available</div>

  const handleUnlinkAccount = async (accountId) => {
    if (!confirm('Are you sure you want to unlink this account?')) {
      return
    }

    try {
      await unlinkAccount(accountId)
      alert('Account unlinked successfully')
    } catch (error) {
      alert(`Failed to unlink account: ${error.message}`)
    }
  }

  return (
    <div className="account-manager">
      <h2>Account Management</h2>
      
      <div className="account-summary">
        <h3>Summary</h3>
        <p>Total Accounts: {backendUser.total_accounts}</p>
        <p>Active Accounts: {backendUser.account_summary.active_accounts}</p>
        {backendUser.account_summary.expired_tokens > 0 && (
          <p className="warning">
            ⚠️ {backendUser.account_summary.expired_tokens} accounts have expired tokens
          </p>
        )}
      </div>

      <div className="primary-account">
        <h3>Primary Account</h3>
        {backendUser.primary_account && (
          <AccountCard 
            account={backendUser.primary_account} 
            isPrimary={true}
          />
        )}
      </div>

      <div className="secondary-accounts">
        <h3>Secondary Accounts ({backendUser.secondary_accounts.length})</h3>
        {backendUser.secondary_accounts.map(account => (
          <AccountCard 
            key={account.id}
            account={account}
            isPrimary={false}
            onUnlink={() => handleUnlinkAccount(account.id)}
          />
        ))}
      </div>
    </div>
  )
}

function AccountCard({ account, isPrimary, onUnlink }) {
  return (
    <div className={`account-card ${isPrimary ? 'primary' : 'secondary'}`}>
      <img src={account.picture} alt="Profile" />
      <div className="account-info">
        <h4>{account.name}</h4>
        <p>{account.email}</p>
        <p className="account-type">
          {isPrimary ? '👑 Primary Account' : '🔗 Secondary Account'}
        </p>
        {account.is_token_expired && (
          <p className="expired">⚠️ Token expired - re-authentication needed</p>
        )}
      </div>
      {!isPrimary && (
        <button 
          onClick={onUnlink}
          className="unlink-button"
        >
          Unlink
        </button>
      )}
    </div>
  )
}
```

## 📊 Monitoring and Analytics Examples

### Example 6: API Usage Analytics

```javascript
/**
 * API usage monitoring and analytics
 * Track performance, errors, and usage patterns
 */
class APIAnalytics {
  constructor() {
    this.metrics = {
      requests: 0,
      errors: 0,
      responseTime: [],
      errorsByType: {},
      endpointUsage: {}
    }
  }

  trackRequest(endpoint, startTime, endTime, success, error = null) {
    this.metrics.requests++
    this.metrics.responseTime.push(endTime - startTime)
    
    // Track endpoint usage
    if (!this.metrics.endpointUsage[endpoint]) {
      this.metrics.endpointUsage[endpoint] = { success: 0, error: 0 }
    }
    
    if (success) {
      this.metrics.endpointUsage[endpoint].success++
    } else {
      this.metrics.errors++
      this.metrics.endpointUsage[endpoint].error++
      
      // Track error types
      const errorCode = error?.code || 'UNKNOWN'
      this.metrics.errorsByType[errorCode] = 
        (this.metrics.errorsByType[errorCode] || 0) + 1
    }
  }

  getAnalytics() {
    const avgResponseTime = this.metrics.responseTime.reduce((a, b) => a + b, 0) 
      / this.metrics.responseTime.length || 0
    
    const errorRate = (this.metrics.errors / this.metrics.requests) * 100 || 0

    return {
      summary: {
        totalRequests: this.metrics.requests,
        totalErrors: this.metrics.errors,
        errorRate: `${errorRate.toFixed(2)}%`,
        avgResponseTime: `${avgResponseTime.toFixed(2)}ms`
      },
      endpoints: this.metrics.endpointUsage,
      errorBreakdown: this.metrics.errorsByType,
      performance: {
        fastestResponse: Math.min(...this.metrics.responseTime) || 0,
        slowestResponse: Math.max(...this.metrics.responseTime) || 0,
        medianResponse: this.getMedian(this.metrics.responseTime)
      }
    }
  }

  getMedian(arr) {
    if (arr.length === 0) return 0
    const sorted = [...arr].sort((a, b) => a - b)
    const mid = Math.floor(sorted.length / 2)
    return sorted.length % 2 === 0 
      ? (sorted[mid - 1] + sorted[mid]) / 2 
      : sorted[mid]
  }

  generateReport() {
    const analytics = this.getAnalytics()
    
    console.log('📊 API Usage Analytics Report')
    console.log('=' .repeat(40))
    console.log(`Total Requests: ${analytics.summary.totalRequests}`)
    console.log(`Error Rate: ${analytics.summary.errorRate}`)
    console.log(`Avg Response Time: ${analytics.summary.avgResponseTime}`)
    console.log()
    
    console.log('🎯 Endpoint Usage:')
    Object.entries(analytics.endpoints).forEach(([endpoint, stats]) => {
      const total = stats.success + stats.error
      const successRate = (stats.success / total * 100).toFixed(1)
      console.log(`  ${endpoint}: ${total} requests (${successRate}% success)`)
    })
    console.log()
    
    console.log('❌ Error Breakdown:')
    Object.entries(analytics.errorBreakdown).forEach(([code, count]) => {
      console.log(`  ${code}: ${count} occurrences`)
    })
    console.log()
    
    console.log('⚡ Performance:')
    console.log(`  Fastest: ${analytics.performance.fastestResponse}ms`)
    console.log(`  Slowest: ${analytics.performance.slowestResponse}ms`)
    console.log(`  Median: ${analytics.performance.medianResponse}ms`)
  }
}

// Enhanced API call function with analytics
const analytics = new APIAnalytics()

async function apiCallWithAnalytics(endpoint, options = {}) {
  const startTime = Date.now()
  let success = false
  let error = null
  
  try {
    const result = await apiCall(endpoint, options)
    success = true
    return result
  } catch (err) {
    error = err
    throw err
  } finally {
    const endTime = Date.now()
    analytics.trackRequest(endpoint, startTime, endTime, success, error)
  }
}

// Example usage with analytics
async function demonstrateAnalytics() {
  console.log('📈 Running API calls with analytics...')
  
  // Make various API calls
  const calls = [
    () => apiCallWithAnalytics('/users/me?user_id=1'),
    () => apiCallWithAnalytics('/users/me?user_id=999'), // Will fail
    () => apiCallWithAnalytics('/auth/save-user', {
      method: 'POST',
      body: JSON.stringify({ invalid: 'data' })
    }), // Will fail
    () => apiCallWithAnalytics('/users/me?user_id=1'),
    () => apiCallWithAnalytics('/users/me?user_id=1'),
  ]
  
  // Execute all calls
  for (const call of calls) {
    try {
      await call()
    } catch (error) {
      // Ignore errors for demo purposes
    }
  }
  
  // Generate analytics report
  analytics.generateReport()
}

await demonstrateAnalytics()
```

## 🧪 Testing Examples

### Example 7: Comprehensive Test Suite

```javascript
/**
 * Complete test suite for API integration
 * Includes unit tests, integration tests, and end-to-end scenarios
 */
class APITestSuite {
  constructor() {
    this.testResults = []
  }

  async runTest(testName, testFunction) {
    console.log(`🧪 Running: ${testName}`)
    const startTime = Date.now()
    
    try {
      await testFunction()
      const duration = Date.now() - startTime
      this.testResults.push({
        name: testName,
        status: 'PASSED',
        duration: `${duration}ms`
      })
      console.log(`✅ ${testName} - PASSED (${duration}ms)`)
    } catch (error) {
      const duration = Date.now() - startTime
      this.testResults.push({
        name: testName,
        status: 'FAILED',
        error: error.message,
        duration: `${duration}ms`
      })
      console.log(`❌ ${testName} - FAILED (${duration}ms)`)
      console.log(`   Error: ${error.message}`)
    }
  }

  // Test user creation
  async testUserCreation() {
    const userData = {
      profile: {
        id: `test-${Date.now()}`,
        email: `test-${Date.now()}@example.com`,
        name: 'Test User'
      },
      tokens: {
        access_token: 'test_token'
      },
      is_primary: true
    }

    const response = await apiCall('/auth/save-user', {
      method: 'POST',
      body: JSON.stringify(userData)
    })

    if (!response.data.user || !response.data.is_new_user) {
      throw new Error('User creation response invalid')
    }

    return response.data.user.id
  }

  // Test user retrieval
  async testUserRetrieval() {
    // First create a user
    const userId = await this.testUserCreation()
    
    // Then retrieve it
    const response = await apiCall(`/users/me?user_id=${userId}`)
    
    if (!response.data || response.data.id !== userId) {
      throw new Error('User retrieval failed or returned wrong user')
    }
  }

  // Test validation errors
  async testValidationErrors() {
    try {
      await apiCall('/auth/save-user', {
        method: 'POST',
        body: JSON.stringify({}) // Empty data should fail validation
      })
      throw new Error('Expected validation error but request succeeded')
    } catch (error) {
      if (error.code !== 'VALIDATION_ERROR') {
        throw new Error(`Expected VALIDATION_ERROR but got ${error.code}`)
      }
      // Test passed - validation error was thrown as expected
    }
  }

  // Test resource not found
  async testResourceNotFound() {
    try {
      await apiCall('/users/me?user_id=999999')
      throw new Error('Expected not found error but request succeeded')
    } catch (error) {
      if (error.code !== 'RESOURCE_NOT_FOUND') {
        throw new Error(`Expected RESOURCE_NOT_FOUND but got ${error.code}`)
      }
      // Test passed
    }
  }

  // Test account linking
  async testAccountLinking() {
    // Create primary user
    const primaryUserId = await this.testUserCreation()
    const primaryUser = await apiCall(`/users/me?user_id=${primaryUserId}`)
    
    // Link secondary account
    const secondaryAccountData = {
      profile: {
        id: `secondary-${Date.now()}`,
        email: primaryUser.data.email, // Same email for linking
        name: 'Secondary Account'
      },
      tokens: {
        access_token: 'secondary_token'
      },
      is_primary: false
    }

    const linkResponse = await apiCall('/auth/save-user', {
      method: 'POST',
      body: JSON.stringify(secondaryAccountData)
    })

    if (!linkResponse.data.account_created || linkResponse.data.is_new_user) {
      throw new Error('Account linking failed - should create account but not new user')
    }

    if (linkResponse.data.user.total_accounts !== 2) {
      throw new Error('Account linking failed - total accounts should be 2')
    }
  }

  // Test account unlinking
  async testAccountUnlinking() {
    // Create user with secondary account (from previous test setup)
    const userId = await this.testUserCreation()
    const user = await apiCall(`/users/me?user_id=${userId}`)
    
    // Create a secondary account to unlink
    await apiCall('/auth/save-user', {
      method: 'POST',
      body: JSON.stringify({
        profile: {
          id: `unlink-test-${Date.now()}`,
          email: user.data.email,
          name: 'To Be Unlinked'
        },
        tokens: { access_token: 'token' },
        is_primary: false
      })
    })

    const updatedUser = await apiCall(`/users/me?user_id=${userId}`)
    
    if (updatedUser.data.secondary_accounts.length === 0) {
      throw new Error('No secondary account found to unlink')
    }

    const accountToUnlink = updatedUser.data.secondary_accounts[0]
    
    const unlinkResponse = await apiCall(`/auth/accounts/${accountToUnlink.id}`, {
      method: 'DELETE'
    })

    if (!unlinkResponse.data.unlinked_account) {
      throw new Error('Account unlinking failed')
    }
  }

  // Test primary account protection
  async testPrimaryAccountProtection() {
    const userId = await this.testUserCreation()
    const user = await apiCall(`/users/me?user_id=${userId}`)
    
    try {
      await apiCall(`/auth/accounts/${user.data.primary_account.id}`, {
        method: 'DELETE'
      })
      throw new Error('Expected forbidden error but primary account was unlinked')
    } catch (error) {
      if (error.code !== 'VALIDATION_ERROR' && error.code !== 'FORBIDDEN') {
        throw new Error(`Expected FORBIDDEN/VALIDATION_ERROR but got ${error.code}`)
      }
      // Test passed
    }
  }

  // Test performance
  async testPerformance() {
    const startTime = Date.now()
    const userId = await this.testUserCreation()
    const creationTime = Date.now() - startTime

    const retrievalStart = Date.now()
    await apiCall(`/users/me?user_id=${userId}`)
    const retrievalTime = Date.now() - retrievalStart

    // Performance thresholds (adjust based on your requirements)
    if (creationTime > 2000) {
      throw new Error(`User creation too slow: ${creationTime}ms (threshold: 2000ms)`)
    }

    if (retrievalTime > 1000) {
      throw new Error(`User retrieval too slow: ${retrievalTime}ms (threshold: 1000ms)`)
    }

    console.log(`   Performance: Creation ${creationTime}ms, Retrieval ${retrievalTime}ms`)
  }

  // Run all tests
  async runAllTests() {
    console.log('🧪 Starting API Test Suite')
    console.log('=' .repeat(50))

    await this.runTest('User Creation', () => this.testUserCreation())
    await this.runTest('User Retrieval', () => this.testUserRetrieval())
    await this.runTest('Validation Errors', () => this.testValidationErrors())
    await this.runTest('Resource Not Found', () => this.testResourceNotFound())
    await this.runTest('Account Linking', () => this.testAccountLinking())
    await this.runTest('Account Unlinking', () => this.testAccountUnlinking())
    await this.runTest('Primary Account Protection', () => this.testPrimaryAccountProtection())
    await this.runTest('Performance', () => this.testPerformance())

    this.generateTestReport()
  }

  generateTestReport() {
    console.log()
    console.log('📊 Test Results Summary')
    console.log('=' .repeat(30))

    const passed = this.testResults.filter(r => r.status === 'PASSED').length
    const failed = this.testResults.filter(r => r.status === 'FAILED').length

    console.log(`Total Tests: ${this.testResults.length}`)
    console.log(`Passed: ${passed}`)
    console.log(`Failed: ${failed}`)
    console.log(`Success Rate: ${(passed / this.testResults.length * 100).toFixed(1)}%`)

    if (failed > 0) {
      console.log()
      console.log('❌ Failed Tests:')
      this.testResults
        .filter(r => r.status === 'FAILED')
        .forEach(test => {
          console.log(`   - ${test.name}: ${test.error}`)
        })
    }

    console.log()
    console.log('🎉 Test suite completed!')
  }
}

// Run the test suite
const testSuite = new APITestSuite()
await testSuite.runAllTests()
```

This comprehensive collection of API examples demonstrates real-world usage patterns, error handling, testing, and integration with popular frameworks. Each example includes detailed error handling, logging, and best practices for production use.

## 🚀 Next Steps

1. **Customize the examples** for your specific use case
2. **Add authentication** headers for production environments  
3. **Implement retry logic** for critical operations
4. **Add monitoring** and alerting for production deployments
5. **Create automated tests** based on the test suite example

These examples provide a solid foundation for integrating with the Subscription Tracker API in any JavaScript/TypeScript application.