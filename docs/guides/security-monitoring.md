# Security & Monitoring Guide

## 🛡️ Enterprise Security Architecture

### Overview
The Subscription Tracker API implements defense-in-depth security with multiple layers of protection, real-time threat detection, and comprehensive monitoring.

## 🔐 OAuth Token Security

### AES-128 Encryption at Rest
All OAuth tokens are encrypted before database storage using enterprise-grade encryption:

```python
# Encryption Implementation
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Key derivation with PBKDF2 (100,000 iterations)
kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b'oauth_token_salt_2024',
    iterations=100000,
)
```

**Security Features:**
- **AES-128 in GCM mode** for authenticated encryption
- **PBKDF2 key derivation** with 100,000 iterations
- **Environment-based master keys** (never stored in code)
- **Per-token unique initialization vectors**

### Token Lifecycle Protection

```python
# Secure token storage flow
{
  "access_token": "ya29.plaintext_token",      # Input
  "access_token_encrypted": "gAAAAABh...",     # Stored
  "expires_at": "2024-01-15T17:00:00Z",       # Expiry tracking
  "token_status": "active",                    # Status management
  "last_token_refresh": "2024-01-15T16:00:00Z" # Lifecycle tracking
}
```

**Protection Mechanisms:**
- ✅ **Encryption at rest**: All tokens encrypted in database
- ✅ **Secure transmission**: HTTPS/TLS 1.3 for all API calls
- ✅ **Memory protection**: Tokens cleared from memory after use
- ✅ **Audit logging**: All token operations logged immutably

---

## 🚨 Advanced Rate Limiting

### Multi-Layer Protection System

```
Request Processing Flow:
┌─────────────────┐
│   Client IP     │
├─────────────────┤
│ IP Reputation   │ ← Progressive penalties
├─────────────────┤  
│ Fixed Window    │ ← Per-minute/hour limits
├─────────────────┤
│ Token Bucket    │ ← Burst protection
├─────────────────┤
│ Endpoint Limits │ ← Category-specific rules
└─────────────────┘
```

### Rate Limit Configuration

| Endpoint Category | Per Minute | Per Hour | Burst | Penalty |
|-------------------|------------|----------|-------|---------|
| **Authentication** | 10 | 100 | 5 | 2.0x |
| **User Management** | 30 | 500 | 10 | 1.5x |
| **Token Operations** | 5 | 50 | 2 | 3.0x |
| **General API** | 60 | 1000 | 20 | 1.2x |

### IP Reputation System

```python
# Reputation tracking
{
  "ip_address": "192.168.1.100",
  "violations": 3,
  "last_violation": "2024-01-15T15:30:00Z",
  "reputation_score": 0.7,
  "penalty_multiplier": 1.5,
  "decay_rate": "24_hour_half_life"
}
```

**Reputation Factors:**
- **Rate limit violations**: -0.2 per violation
- **Authentication failures**: -0.1 per failure  
- **Successful requests**: +0.01 per success (slow recovery)
- **Time decay**: 50% reduction every 24 hours

### Progressive Penalties

1. **First Violation**: Standard rate limits applied
2. **Repeat Violations**: Limits reduced by penalty multiplier
3. **Persistent Abuse**: IP blocked for cooling-off period
4. **Recovery**: Gradual reputation improvement over time

---

## 📋 Immutable Audit Trail

### Cryptographic Integrity Protection

```python
# Audit record with integrity protection
{
  "id": 1001,
  "action": "token_refresh", 
  "status": "success",
  "entity_type": "LinkedAccount",
  "entity_id": 123,
  "user_id": 456,
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "details": {"account_email": "user@example.com"},
  "created_at": "2024-01-15T16:00:00Z",
  "hash_value": "a7b2c3d4e5f6789...",     # SHA-256 hash
  "previous_hash": "9f8e7d6c5b4a3...",      # Chain link
  "integrity_verified": true
}
```

### Hash Chain Verification

```python
# Integrity verification process
def verify_audit_chain():
    logs = get_audit_logs_ordered()
    previous_hash = None
    
    for log in logs:
        # Verify individual record hash
        calculated_hash = calculate_hash(log)
        if calculated_hash != log.hash_value:
            return {"valid": False, "error": "Hash mismatch"}
        
        # Verify chain continuity  
        if previous_hash and log.previous_hash != previous_hash:
            return {"valid": False, "error": "Chain break"}
            
        previous_hash = log.hash_value
    
    return {"valid": True, "records_verified": len(logs)}
```

### Comprehensive Event Tracking

**User Actions:**
- Account creation/updates
- Account linking/unlinking
- Login/logout events
- Profile modifications

**System Events:**
- Token refresh operations
- Background task executions
- Database migrations
- System startup/shutdown

**Security Events:**
- Authentication failures
- Rate limit violations
- Unauthorized access attempts
- Token revocations

---

## 🔍 Real-Time Threat Detection

### Behavioral Anomaly Detection

```python
# Suspicious activity patterns
THREAT_PATTERNS = {
    "credential_stuffing": {
        "pattern": "multiple_failed_logins",
        "threshold": 5,
        "window": 300,  # 5 minutes
        "severity": "high"
    },
    "token_harvesting": {
        "pattern": "rapid_token_refresh",
        "threshold": 10,
        "window": 60,   # 1 minute  
        "severity": "critical"
    },
    "account_enumeration": {
        "pattern": "sequential_user_id_access",
        "threshold": 20,
        "window": 300,
        "severity": "medium"
    }
}
```

### Automated Response System

**Threat Response Escalation:**
1. **Detection**: Pattern matching triggers alert
2. **Classification**: Risk severity assessment
3. **Response**: Automated countermeasures
4. **Notification**: Alert appropriate channels
5. **Investigation**: Generate detailed forensics

**Response Actions:**
- **Low Risk**: Increased monitoring, log annotation
- **Medium Risk**: Rate limit tightening, security team notification
- **High Risk**: Temporary IP blocking, incident response
- **Critical**: Emergency contact, system isolation

---

## 📊 Multi-Channel Alerting

### Alert Severity Matrix

| Severity | Response Time | Channels | Escalation |
|----------|---------------|----------|------------|
| **Critical** | <5 minutes | PagerDuty + Email + SMS + Webhook | On-call engineer |
| **High** | <15 minutes | Email + Webhook | Security team |
| **Medium** | <1 hour | Email | Development team |
| **Low** | Daily digest | Email | System logs |

### Custom Webhook Integration

```json
{
  "text": "🔴 Critical Security Alert",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "🔴 Token Refresh Failures Detected"
      }
    },
    {
      "type": "section", 
      "fields": [
        {"type": "mrkdwn", "text": "*Severity:* CRITICAL"},
        {"type": "mrkdwn", "text": "*Environment:* Production"},
        {"type": "mrkdwn", "text": "*Failed Accounts:* 15"},
        {"type": "mrkdwn", "text": "*Time Window:* Last 5 minutes"},
        {"type": "mrkdwn", "text": "*Affected Users:* 12"},
        {"type": "mrkdwn", "text": "*Geographic Pattern:* US-West concentrated"}
      ]
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": {"type": "plain_text", "text": "View Dashboard"},
          "url": "https://monitoring.example.com/incident/abc123"
        },
        {
          "type": "button", 
          "text": {"type": "plain_text", "text": "Incident Response"},
          "url": "https://runbook.example.com/token-failures"
        }
      ]
    }
  ]
}
```

### PagerDuty Integration

```python
# Critical incident creation
pagerduty_payload = {
  "routing_key": "YOUR_INTEGRATION_KEY",
  "event_action": "trigger",
  "payload": {
    "summary": "OAuth Token System Failure - 15 accounts affected",
    "severity": "critical",
    "source": "subscription-tracker-prod",
    "component": "token_refresh_system",
    "group": "authentication",
    "class": "oauth_failure",
    "custom_details": {
      "failed_accounts": 15,
      "error_rate": "12%",
      "geographic_impact": "US-West",
      "estimated_user_impact": "~1,200 users"
    }
  }
}
```

---

## 📈 Performance Monitoring

### Sentry Error Tracking

```python
# Sentry configuration with PII filtering
sentry_sdk.init(
    dsn="https://your-sentry-dsn",
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration(), 
        RedisIntegration(),
        CeleryIntegration()
    ],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    before_send=filter_sensitive_data,
    environment="production"
)

def filter_sensitive_data(event, hint):
    # Remove OAuth tokens from error reports
    if 'request' in event and 'data' in event['request']:
        sensitive_fields = ['access_token', 'refresh_token', 'id_token']
        for field in sensitive_fields:
            if field in event['request']['data']:
                event['request']['data'][field] = '[Redacted]'
    return event
```

### Application Performance Monitoring

**Key Metrics:**
- **Response Times**: P50, P95, P99 percentiles
- **Error Rates**: 4xx/5xx response tracking  
- **Token Operations**: Refresh success rates, timing
- **Database Performance**: Query times, connection pool usage
- **Background Tasks**: Task completion rates, queue depths

### Custom Metrics Dashboard

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'Request duration')

# Token metrics  
TOKEN_REFRESH_SUCCESS = Counter('token_refresh_success_total', 'Successful token refreshes')
TOKEN_REFRESH_FAILURES = Counter('token_refresh_failures_total', 'Failed token refreshes', ['error_type'])

# Security metrics
RATE_LIMIT_VIOLATIONS = Counter('rate_limit_violations_total', 'Rate limit violations', ['ip_range'])
AUTH_FAILURES = Counter('auth_failures_total', 'Authentication failures', ['failure_type'])
```

---

## 🚨 Incident Response

### Security Incident Playbook

**Phase 1: Detection & Assessment (0-15 minutes)**
1. **Alert Triage**: Classify severity and impact
2. **Initial Assessment**: Gather basic incident details
3. **Stakeholder Notification**: Alert appropriate teams
4. **Evidence Preservation**: Capture logs and system state

**Phase 2: Containment (15-60 minutes)**  
1. **Threat Isolation**: Block malicious IPs if needed
2. **Service Protection**: Implement additional rate limiting
3. **User Communication**: Notify affected users if necessary
4. **System Stabilization**: Ensure service availability

**Phase 3: Investigation (1-4 hours)**
1. **Root Cause Analysis**: Deep dive into incident cause
2. **Impact Assessment**: Determine scope of compromise
3. **Evidence Collection**: Gather comprehensive forensics
4. **Timeline Reconstruction**: Map incident progression

**Phase 4: Recovery & Lessons Learned**
1. **System Hardening**: Implement additional protections
2. **Process Improvement**: Update security procedures  
3. **Documentation**: Record incident details and response
4. **Team Training**: Share learnings with broader team

### Emergency Contacts

| Role | Primary | Secondary | Escalation |
|------|---------|-----------|------------|
| **Security Lead** | security@company.com | +1-555-SECURITY | CISO |
| **On-Call Engineer** | oncall@company.com | +1-555-ONCALL | Engineering Manager |
| **Product Owner** | product@company.com | +1-555-PRODUCT | Head of Product |
| **Legal/Compliance** | legal@company.com | +1-555-LEGAL | General Counsel |

### Compliance & Reporting

**Regulatory Requirements:**
- **GDPR Article 33**: Breach notification within 72 hours
- **SOC 2 Type II**: Continuous monitoring and reporting
- **ISO 27001**: Information security management
- **PCI DSS**: If processing payment data (future)

**Incident Documentation:**
```json
{
  "incident_id": "INC-2024-001",
  "severity": "high",
  "detected_at": "2024-01-15T16:00:00Z",
  "resolved_at": "2024-01-15T18:30:00Z",
  "affected_systems": ["token_refresh", "user_authentication"],
  "affected_users": 1250,
  "root_cause": "Third-party OAuth provider outage",
  "remediation_actions": [
    "Implemented fallback token validation",
    "Added circuit breaker for OAuth calls",
    "Enhanced monitoring for provider health"
  ],
  "lessons_learned": [
    "Need redundant OAuth providers",
    "Improve failover automation",
    "Better user communication during outages"
  ]
}
```

This comprehensive security and monitoring system provides **enterprise-grade protection** with **real-time threat detection**, **automated response**, and **complete audit transparency**! 🛡️