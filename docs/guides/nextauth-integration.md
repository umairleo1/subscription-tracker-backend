# NextAuth.js Integration Guide

This guide provides step-by-step instructions for integrating the Subscription Tracker API with NextAuth.js for seamless Google OAuth authentication and multi-account management.

## 🎯 Overview

NextAuth.js handles the OAuth flow on the frontend, while our Subscription Tracker API manages user data, account linking, and business logic on the backend. This creates a robust, scalable authentication system.

**Architecture Flow:**
1. User clicks "Sign in with Google" in your app
2. NextAuth.js redirects to Google OAuth
3. Google returns OAuth data to NextAuth.js
4. NextAuth.js sends OAuth data to your Subscription Tracker API
5. API creates/updates user and returns comprehensive user data
6. NextAuth.js stores user session with backend user ID

## 🚀 Setup Instructions

### 1. Install NextAuth.js

```bash
npm install next-auth
# or
yarn add next-auth
# or
pnpm add next-auth
```

### 2. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google+ API and Gmail API (if needed for subscriptions)
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Configure OAuth consent screen
6. Add authorized redirect URIs:
   - `http://localhost:3000/api/auth/callback/google` (development)
   - `https://yourdomain.com/api/auth/callback/google` (production)

### 3. Environment Variables

Create `.env.local` in your Next.js project:

```bash
# NextAuth.js Configuration
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret-key-here

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Backend API
BACKEND_API_URL=http://localhost:8000/api/v1
```

## 🔧 NextAuth.js Configuration

### Complete NextAuth.js Setup

Create `pages/api/auth/[...nextauth].js`:

```javascript
import NextAuth from 'next-auth'
import GoogleProvider from 'next-auth/providers/google'

// Backend API client
class SubscriptionTrackerAPI {
  constructor() {
    this.baseURL = process.env.BACKEND_API_URL
  }

  async saveUser(profile, account, isPrimary = true) {
    try {
      const response = await fetch(`${this.baseURL}/auth/save-user`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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
            id_token: account.id_token,
            expires_at: account.expires_at,
            token_type: account.token_type || 'Bearer',
            scope: account.scope
          },
          is_primary: isPrimary
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(`Backend API Error: ${errorData.message}`)
      }

      const data = await response.json()
      return data.data
    } catch (error) {
      console.error('❌ Failed to save user to backend:', error.message)
      throw error
    }
  }

  async getUser(userId) {
    try {
      const response = await fetch(`${this.baseURL}/users/me?user_id=${userId}`)
      
      if (response.status === 404) {
        return null // User not found
      }
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(`Backend API Error: ${errorData.message}`)
      }

      const data = await response.json()
      return data.data
    } catch (error) {
      console.error('❌ Failed to fetch user from backend:', error.message)
      return null
    }
  }

  async refreshUserData(userId) {
    return this.getUser(userId)
  }
}

const api = new SubscriptionTrackerAPI()

export default NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      authorization: {
        params: {
          // Request comprehensive scopes for subscription tracking
          scope: [
            'openid',
            'email', 
            'profile',
            'https://www.googleapis.com/auth/gmail.readonly'
          ].join(' '),
          // Force account selection for multi-account support
          prompt: 'select_account',
          // Request offline access for refresh tokens
          access_type: 'offline'
        }
      }
    })
  ],

  pages: {
    signIn: '/auth/signin',    // Custom sign-in page (optional)
    error: '/auth/error',      // Custom error page (optional)
  },

  callbacks: {
    async signIn({ user, account, profile, email, credentials }) {
      try {
        console.log(`🔐 Processing sign-in for: ${profile.email}`)
        
        // Save user to backend API
        const backendUser = await api.saveUser(profile, account, true)
        
        // Attach backend data to user object for later use
        user.backendId = backendUser.user.id
        user.isNewUser = backendUser.is_new_user
        user.accountCreated = backendUser.account_created
        user.totalAccounts = backendUser.user.total_accounts
        user.hasExpiredTokens = backendUser.user.account_summary?.expired_tokens > 0
        
        console.log(`✅ User processed - Backend ID: ${user.backendId}, New: ${user.isNewUser}`)
        
        return true
      } catch (error) {
        console.error('❌ Sign-in callback failed:', error.message)
        
        // In development, log the full error
        if (process.env.NODE_ENV === 'development') {
          console.error('Full error:', error)
        }
        
        // You can choose to fail the sign-in or allow it to continue
        // For this example, we'll allow it but the user won't have backend data
        return true
      }
    },

    async jwt({ token, user, account, profile }) {
      // Initial sign in - store backend user data in JWT
      if (user) {
        token.backendId = user.backendId
        token.isNewUser = user.isNewUser
        token.accountCreated = user.accountCreated
        token.totalAccounts = user.totalAccounts
        token.hasExpiredTokens = user.hasExpiredTokens
        token.lastSync = Date.now()
      }

      // Refresh backend user data periodically (every 5 minutes)
      const shouldRefresh = Date.now() > (token.lastSync || 0) + (5 * 60 * 1000)
      
      if (token.backendId && shouldRefresh) {
        try {
          console.log(`🔄 Refreshing user data for backend ID: ${token.backendId}`)
          const freshUserData = await api.refreshUserData(token.backendId)
          
          if (freshUserData) {
            token.totalAccounts = freshUserData.total_accounts
            token.hasExpiredTokens = freshUserData.account_summary?.expired_tokens > 0
            token.lastSync = Date.now()
            console.log(`✅ User data refreshed - Accounts: ${token.totalAccounts}`)
          }
        } catch (error) {
          console.error('❌ Failed to refresh user data:', error.message)
        }
      }

      return token
    },

    async session({ session, token }) {
      // Include backend data in the session
      if (token.backendId) {
        session.user.backendId = token.backendId
        session.user.isNewUser = token.isNewUser
        session.user.accountCreated = token.accountCreated
        session.user.totalAccounts = token.totalAccounts
        session.user.hasExpiredTokens = token.hasExpiredTokens
        session.user.lastSync = token.lastSync
      }

      return session
    },

    async redirect({ url, baseUrl }) {
      // Allows relative callback URLs
      if (url.startsWith('/')) return `${baseUrl}${url}`
      // Allows callback URLs on the same origin
      else if (new URL(url).origin === baseUrl) return url
      return baseUrl
    }
  },

  events: {
    async signIn({ user, account, profile, isNewUser }) {
      console.log(`📊 Sign-in event: ${profile.email}`)
      console.log(`   Backend ID: ${user.backendId}`)
      console.log(`   Is New User: ${user.isNewUser}`)
      console.log(`   Total Accounts: ${user.totalAccounts}`)
    },

    async signOut({ session, token }) {
      console.log(`👋 Sign-out event for backend ID: ${token?.backendId}`)
    },

    async createUser({ user }) {
      console.log(`👤 User created in NextAuth database: ${user.email}`)
    },

    async linkAccount({ user, account, profile }) {
      console.log(`🔗 Account linked: ${account.provider} for ${user.email}`)
    }
  },

  // Session configuration
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
    updateAge: 24 * 60 * 60,   // 24 hours
  },

  // JWT configuration
  jwt: {
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },

  // Enable debug messages in development
  debug: process.env.NODE_ENV === 'development',
})
```

## 🎨 Frontend Integration

### 1. Session Provider Setup

Wrap your app with the SessionProvider in `pages/_app.js`:

```javascript
import { SessionProvider } from 'next-auth/react'
import '../styles/globals.css'

export default function App({
  Component,
  pageProps: { session, ...pageProps },
}) {
  return (
    <SessionProvider session={session}>
      <Component {...pageProps} />
    </SessionProvider>
  )
}
```

### 2. Authentication Components

Create reusable authentication components:

```javascript
// components/auth/SignInButton.jsx
import { signIn, signOut, useSession } from 'next-auth/react'

export function SignInButton() {
  const { data: session, status } = useSession()

  if (status === 'loading') {
    return <button disabled>Loading...</button>
  }

  if (session) {
    return (
      <div className="user-menu">
        <img src={session.user.image} alt="Profile" className="profile-image" />
        <div className="user-info">
          <p>Welcome, {session.user.name}!</p>
          {session.user.totalAccounts > 1 && (
            <p className="account-count">
              📧 {session.user.totalAccounts} accounts linked
            </p>
          )}
          {session.user.hasExpiredTokens && (
            <p className="warning">⚠️ Some tokens need refresh</p>
          )}
        </div>
        <button onClick={() => signOut()} className="sign-out-btn">
          Sign Out
        </button>
      </div>
    )
  }

  return (
    <button 
      onClick={() => signIn('google')} 
      className="sign-in-btn"
    >
      <img src="/google-icon.svg" alt="Google" />
      Sign in with Google
    </button>
  )
}

// components/auth/ProtectedRoute.jsx
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/router'
import { useEffect } from 'react'

export function ProtectedRoute({ children }) {
  const { data: session, status } = useSession()
  const router = useRouter()

  useEffect(() => {
    if (status === 'loading') return // Still loading

    if (!session) {
      router.push('/auth/signin')
    }
  }, [session, status, router])

  if (status === 'loading') {
    return <div>Loading...</div>
  }

  if (!session) {
    return null
  }

  return children
}
```

### 3. Multi-Account Management Hook

Create a custom hook for managing multiple accounts:

```javascript
// hooks/useMultiAccount.js
import { useSession } from 'next-auth/react'
import { useState, useEffect, useCallback } from 'react'

export function useMultiAccount() {
  const { data: session } = useSession()
  const [accounts, setAccounts] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch complete account data from backend
  const fetchAccounts = useCallback(async () => {
    if (!session?.user?.backendId) return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/backend/users/${session.user.backendId}`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch account data')
      }

      const data = await response.json()
      setAccounts(data.data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [session?.user?.backendId])

  // Link additional Google account
  const linkAccount = async () => {
    try {
      // Trigger Google OAuth for additional account
      const result = await signIn('google', {
        redirect: false,
        callbackUrl: window.location.pathname
      })

      if (result?.ok) {
        // Refresh account data
        await fetchAccounts()
        return { success: true }
      } else {
        throw new Error(result?.error || 'Failed to link account')
      }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // Unlink Google account
  const unlinkAccount = async (accountId) => {
    try {
      const response = await fetch(`/api/backend/auth/accounts/${accountId}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.message)
      }

      // Refresh account data
      await fetchAccounts()
      return { success: true }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // Load accounts on mount
  useEffect(() => {
    fetchAccounts()
  }, [fetchAccounts])

  return {
    accounts,
    loading,
    error,
    linkAccount,
    unlinkAccount,
    refresh: fetchAccounts
  }
}
```

### 4. Account Management Component

```javascript
// components/AccountManager.jsx
import { useMultiAccount } from '../hooks/useMultiAccount'
import { useSession } from 'next-auth/react'
import { useState } from 'react'

export function AccountManager() {
  const { data: session } = useSession()
  const { accounts, loading, error, linkAccount, unlinkAccount, refresh } = useMultiAccount()
  const [actionLoading, setActionLoading] = useState(false)

  const handleLinkAccount = async () => {
    setActionLoading(true)
    
    const result = await linkAccount()
    
    if (result.success) {
      alert('Account linked successfully!')
    } else {
      alert(`Failed to link account: ${result.error}`)
    }
    
    setActionLoading(false)
  }

  const handleUnlinkAccount = async (accountId, accountEmail) => {
    if (!confirm(`Are you sure you want to unlink ${accountEmail}?`)) {
      return
    }

    setActionLoading(true)
    
    const result = await unlinkAccount(accountId)
    
    if (result.success) {
      alert('Account unlinked successfully!')
    } else {
      alert(`Failed to unlink account: ${result.error}`)
    }
    
    setActionLoading(false)
  }

  if (loading) return <div>Loading account information...</div>
  if (error) return <div>Error loading accounts: {error}</div>
  if (!accounts) return <div>No account data available</div>

  return (
    <div className="account-manager">
      <div className="header">
        <h2>Account Management</h2>
        <button 
          onClick={refresh}
          disabled={actionLoading}
          className="refresh-btn"
        >
          🔄 Refresh
        </button>
      </div>

      {/* Account Summary */}
      <div className="account-summary">
        <div className="summary-card">
          <h3>📊 Summary</h3>
          <p>Total Accounts: <strong>{accounts.total_accounts}</strong></p>
          <p>Active: <strong>{accounts.account_summary.active_accounts}</strong></p>
          {accounts.account_summary.expired_tokens > 0 && (
            <p className="warning">
              ⚠️ <strong>{accounts.account_summary.expired_tokens}</strong> tokens expired
            </p>
          )}
        </div>
      </div>

      {/* Primary Account */}
      <div className="primary-account">
        <h3>👑 Primary Account</h3>
        {accounts.primary_account && (
          <AccountCard 
            account={accounts.primary_account} 
            isPrimary={true}
          />
        )}
      </div>

      {/* Secondary Accounts */}
      <div className="secondary-accounts">
        <div className="section-header">
          <h3>🔗 Secondary Accounts ({accounts.secondary_accounts.length})</h3>
          <button 
            onClick={handleLinkAccount}
            disabled={actionLoading || accounts.total_accounts >= 5}
            className="link-account-btn"
          >
            {actionLoading ? 'Linking...' : '+ Link New Account'}
          </button>
        </div>

        {accounts.secondary_accounts.length === 0 ? (
          <p className="no-accounts">No secondary accounts linked</p>
        ) : (
          <div className="accounts-grid">
            {accounts.secondary_accounts.map(account => (
              <AccountCard 
                key={account.id}
                account={account}
                isPrimary={false}
                onUnlink={() => handleUnlinkAccount(account.id, account.email)}
                actionLoading={actionLoading}
              />
            ))}
          </div>
        )}
      </div>

      {/* Account Limit Warning */}
      {accounts.total_accounts >= 5 && (
        <div className="limit-warning">
          ⚠️ You've reached the maximum of 5 Google accounts. 
          Remove an account to link a new one.
        </div>
      )}
    </div>
  )
}

function AccountCard({ account, isPrimary, onUnlink, actionLoading }) {
  return (
    <div className={`account-card ${isPrimary ? 'primary' : 'secondary'}`}>
      <div className="account-avatar">
        <img src={account.picture} alt={account.name} />
        {isPrimary && <div className="primary-badge">👑</div>}
      </div>
      
      <div className="account-details">
        <h4>{account.name}</h4>
        <p className="account-email">{account.email}</p>
        <p className="account-type">
          {isPrimary ? 'Primary Account' : 'Secondary Account'}
        </p>
        
        {account.is_token_expired ? (
          <p className="token-status expired">⚠️ Token expired</p>
        ) : (
          <p className="token-status valid">✅ Token valid</p>
        )}
        
        <p className="last-login">
          Last login: {new Date(account.last_login_at).toLocaleDateString()}
        </p>
      </div>
      
      {!isPrimary && onUnlink && (
        <button 
          onClick={onUnlink}
          disabled={actionLoading}
          className="unlink-btn"
        >
          Unlink
        </button>
      )}
    </div>
  )
}
```

## 🏗️ Backend API Routes

Create Next.js API routes to proxy requests to your backend:

```javascript
// pages/api/backend/users/[userId].js
import { getSession } from 'next-auth/react'

export default async function handler(req, res) {
  const session = await getSession({ req })
  
  if (!session) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const { userId } = req.query
  
  try {
    const backendResponse = await fetch(
      `${process.env.BACKEND_API_URL}/users/me?user_id=${userId}`
    )
    
    const data = await backendResponse.json()
    
    res.status(backendResponse.status).json(data)
  } catch (error) {
    res.status(500).json({ error: 'Internal server error' })
  }
}

// pages/api/backend/auth/accounts/[accountId].js
import { getSession } from 'next-auth/react'

export default async function handler(req, res) {
  if (req.method !== 'DELETE') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const session = await getSession({ req })
  
  if (!session) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const { accountId } = req.query
  
  try {
    const backendResponse = await fetch(
      `${process.env.BACKEND_API_URL}/auth/accounts/${accountId}`,
      {
        method: 'DELETE'
      }
    )
    
    const data = await backendResponse.json()
    
    res.status(backendResponse.status).json(data)
  } catch (error) {
    res.status(500).json({ error: 'Internal server error' })
  }
}
```

## 🎨 Styling

Add CSS for the account management components:

```css
/* styles/account-manager.css */
.account-manager {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.account-summary {
  margin-bottom: 30px;
}

.summary-card {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
}

.summary-card h3 {
  margin-top: 0;
  color: #495057;
}

.warning {
  color: #dc3545;
  font-weight: 500;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.accounts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.account-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  position: relative;
}

.account-card.primary {
  border-color: #ffc107;
  background: #fff8e1;
}

.account-avatar {
  position: relative;
  margin-bottom: 15px;
}

.account-avatar img {
  width: 50px;
  height: 50px;
  border-radius: 50%;
}

.primary-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background: #ffc107;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.account-details h4 {
  margin: 0 0 5px 0;
  color: #212529;
}

.account-email {
  color: #6c757d;
  margin: 0 0 10px 0;
}

.account-type {
  font-size: 14px;
  color: #495057;
  margin: 0 0 10px 0;
}

.token-status {
  font-size: 14px;
  margin: 0 0 10px 0;
}

.token-status.expired {
  color: #dc3545;
}

.token-status.valid {
  color: #28a745;
}

.last-login {
  font-size: 12px;
  color: #6c757d;
  margin: 0 0 15px 0;
}

.unlink-btn {
  background: #dc3545;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  align-self: flex-start;
}

.unlink-btn:hover {
  background: #c82333;
}

.unlink-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.link-account-btn {
  background: #007bff;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}

.link-account-btn:hover {
  background: #0056b3;
}

.link-account-btn:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.limit-warning {
  background: #fff3cd;
  color: #856404;
  padding: 12px;
  border: 1px solid #ffeeba;
  border-radius: 4px;
  margin-top: 20px;
}

.no-accounts {
  color: #6c757d;
  font-style: italic;
  text-align: center;
  padding: 40px;
}
```

## 🧪 Testing Your Integration

### 1. Basic Authentication Test

```javascript
// Test basic sign-in flow
import { render, screen, fireEvent } from '@testing-library/react'
import { SessionProvider } from 'next-auth/react'
import { SignInButton } from '../components/auth/SignInButton'

// Mock NextAuth
jest.mock('next-auth/react')

test('renders sign-in button when not authenticated', () => {
  require('next-auth/react').useSession.mockReturnValue({
    data: null,
    status: 'unauthenticated'
  })

  render(
    <SessionProvider session={null}>
      <SignInButton />
    </SessionProvider>
  )

  expect(screen.getByText('Sign in with Google')).toBeInTheDocument()
})
```

### 2. Manual Testing Checklist

- [ ] Sign in with Google account
- [ ] Verify user data is saved to backend
- [ ] Link a secondary Google account
- [ ] Verify account appears in account manager
- [ ] Unlink secondary account
- [ ] Try to unlink primary account (should fail)
- [ ] Test account limit (try to add 6th account)
- [ ] Sign out and sign back in
- [ ] Verify session persistence

## 🚨 Troubleshooting

### Common Issues

1. **OAuth Redirect Error**
   - Verify redirect URI in Google Console matches exactly
   - Check NEXTAUTH_URL environment variable

2. **Backend API Connection Failed**
   - Verify BACKEND_API_URL is correct
   - Check if backend server is running
   - Verify CORS settings allow your frontend domain

3. **Session Not Persisting**
   - Check NEXTAUTH_SECRET is set
   - Verify JWT configuration
   - Check browser cookies are enabled

4. **Account Linking Failed**
   - Verify is_primary is set to false for secondary accounts
   - Check account limits (max 5 accounts)
   - Ensure same email is used for linking

5. **Token Refresh Issues**
   - Verify access_type: 'offline' in Google provider config
   - Check refresh_token is being stored
   - Implement token refresh logic in your backend

### Debug Mode

Enable debug logging in development:

```javascript
// In your NextAuth config
debug: process.env.NODE_ENV === 'development'
```

### Logging

Add comprehensive logging:

```javascript
// In your NextAuth callbacks
console.log('Sign-in attempt:', { email: profile.email, provider: account.provider })
console.log('Backend response:', backendResponse)
console.log('Session data:', session)
```

## 🚀 Production Considerations

1. **Security**
   - Use HTTPS in production
   - Secure NEXTAUTH_SECRET with strong random key
   - Implement CSRF protection
   - Validate all backend API responses

2. **Performance**
   - Implement caching for user data
   - Use SWR or React Query for data fetching
   - Optimize session refresh frequency

3. **Error Handling**
   - Implement comprehensive error boundaries
   - Add user-friendly error messages
   - Set up error monitoring (Sentry, etc.)

4. **Monitoring**
   - Track authentication success/failure rates
   - Monitor backend API response times
   - Set up alerts for authentication errors

This integration guide provides everything you need to implement secure, scalable multi-account Google OAuth authentication with NextAuth.js and the Subscription Tracker API.