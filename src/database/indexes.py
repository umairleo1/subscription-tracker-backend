"""
Database index definitions and performance optimizations
Critical indexes for PostgreSQL performance at scale
"""
from sqlalchemy import Index, text
from src.domain.entities.user import User
from src.domain.entities.linked_account import LinkedAccount
from src.domain.entities.audit_log import AuditLog
from src.domain.entities.subscription import Subscription
import logging

logger = logging.getLogger(__name__)

# Performance-critical indexes for Users table
user_indexes = [
    # Primary lookup by email (unique already creates index)
    Index('idx_users_email_active', User.email, User.is_active),
    
    # Subscription queries
    Index('idx_users_subscription', User.subscription_plan, User.subscription_status),
    Index('idx_users_subscription_expiry', User.subscription_expires_at),
    
    # Temporal queries
    Index('idx_users_created_at', User.created_at),
    Index('idx_users_last_login', User.last_login_at),
    
    # Composite index for user listing with filters
    Index('idx_users_active_created', User.is_active, User.created_at.desc()),
]

# Critical indexes for LinkedAccount table (high-frequency queries)
linked_account_indexes = [
    # Primary foreign key (usually auto-indexed but explicit for clarity)
    Index('idx_linked_accounts_user_id', LinkedAccount.user_id),
    
    # Google ID lookups (prevent duplicate linking)
    Index('idx_linked_accounts_google_id', LinkedAccount.google_id),
    
    # User account queries (most common pattern)
    Index('idx_linked_accounts_user_active', LinkedAccount.user_id, LinkedAccount.is_active),
    Index('idx_linked_accounts_user_primary', LinkedAccount.user_id, LinkedAccount.is_primary),
    
    # Token management queries
    Index('idx_linked_accounts_token_status', LinkedAccount.token_status, LinkedAccount.is_active),
    Index('idx_linked_accounts_needs_reauth', LinkedAccount.needs_reauth, LinkedAccount.is_active),
    Index('idx_linked_accounts_expires_at', LinkedAccount.expires_at),
    
    # Background job queries (token refresh automation)
    Index('idx_linked_accounts_expiring_tokens', 
          LinkedAccount.expires_at, LinkedAccount.is_active, LinkedAccount.needs_reauth),
    
    # Email lookups for account management
    Index('idx_linked_accounts_email', LinkedAccount.email),
    
    # Temporal queries for cleanup and analytics
    Index('idx_linked_accounts_connected_at', LinkedAccount.connected_at),
    Index('idx_linked_accounts_last_used', LinkedAccount.last_used_at),
    
    # Composite index for admin queries
    Index('idx_linked_accounts_status_created', 
          LinkedAccount.token_status, LinkedAccount.created_at.desc()),
]

# Audit log indexes (write-heavy, read for analysis)
audit_log_indexes = [
    # Primary query patterns
    Index('idx_audit_logs_action', AuditLog.action),
    Index('idx_audit_logs_status', AuditLog.status),
    Index('idx_audit_logs_created_at', AuditLog.created_at.desc()),
    
    # Entity tracking
    Index('idx_audit_logs_entity', AuditLog.entity_type, AuditLog.entity_id),
    Index('idx_audit_logs_user_id', AuditLog.user_id),
    
    # Security and monitoring queries
    Index('idx_audit_logs_ip_address', AuditLog.ip_address),
    Index('idx_audit_logs_session', AuditLog.session_id),
    Index('idx_audit_logs_request', AuditLog.request_id),
    
    # Integrity checking
    Index('idx_audit_logs_hash', AuditLog.hash_value),
    
    # Composite indexes for common query patterns
    Index('idx_audit_logs_user_action_time', 
          AuditLog.user_id, AuditLog.action, AuditLog.created_at.desc()),
    Index('idx_audit_logs_action_status_time', 
          AuditLog.action, AuditLog.status, AuditLog.created_at.desc()),
    
    # System vs user actions
    Index('idx_audit_logs_system_created', 
          AuditLog.created_by_system, AuditLog.created_at.desc()),
    
    # Time-range queries for reporting
    Index('idx_audit_logs_daily_report', 
          text("date_trunc('day', created_at), action, status")),
]

# PostgreSQL-specific optimizations
postgresql_optimizations = [
    # Partial indexes for active records only (smaller, faster)
    Index('idx_users_active_email', User.email, 
          postgresql_where=User.is_active == True),
    
    Index('idx_linked_accounts_active_user', LinkedAccount.user_id, LinkedAccount.email,
          postgresql_where=LinkedAccount.is_active == True),
    
    Index('idx_linked_accounts_expiring_soon', 
          LinkedAccount.user_id, LinkedAccount.expires_at,
          postgresql_where=text("expires_at <= NOW() + INTERVAL '1 hour' AND is_active = true AND needs_reauth = false")),
    
    # Expression indexes for computed values
    Index('idx_users_name_search', 
          text("lower(name)"), postgresql_using='gin'),  # For full-text search
    
    Index('idx_linked_accounts_token_age', 
          text("extract(epoch from (NOW() - last_token_refresh))"),
          postgresql_where=LinkedAccount.is_active == True),
]

def create_performance_indexes(engine):
    """
    Create performance-critical indexes
    Run this during deployment/migration
    """
    try:
        with engine.connect() as conn:
            # Create indexes if they don't exist
            all_indexes = user_indexes + linked_account_indexes + audit_log_indexes + postgresql_optimizations
            
            for index in all_indexes:
                try:
                    index.create(conn, checkfirst=True)
                    logger.info(f"Created index: {index.name}")
                except Exception as e:
                    logger.warning(f"Failed to create index {index.name}: {str(e)}")
            
            # PostgreSQL-specific optimizations
            if engine.dialect.name == 'postgresql':
                _apply_postgresql_optimizations(conn)
                
            logger.info("Performance indexes created successfully")
            
    except Exception as e:
        logger.error(f"Failed to create performance indexes: {str(e)}")
        raise

def _apply_postgresql_optimizations(conn):
    """Apply PostgreSQL-specific performance optimizations"""
    optimizations = [
        # Enable auto-vacuum for high-write tables
        "ALTER TABLE audit_logs SET (autovacuum_vacuum_scale_factor = 0.1);",
        "ALTER TABLE linked_accounts SET (autovacuum_vacuum_scale_factor = 0.2);",
        
        # Optimize statistics for better query planning
        "ALTER TABLE users ALTER COLUMN email SET STATISTICS 1000;",
        "ALTER TABLE linked_accounts ALTER COLUMN user_id SET STATISTICS 1000;",
        "ALTER TABLE linked_accounts ALTER COLUMN expires_at SET STATISTICS 500;",
        "ALTER TABLE audit_logs ALTER COLUMN action SET STATISTICS 500;",
        "ALTER TABLE audit_logs ALTER COLUMN created_at SET STATISTICS 1000;",
        
        # Create extensions if they don't exist
        "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;",  # Query performance monitoring
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;",  # Trigram matching for fuzzy search
        "CREATE EXTENSION IF NOT EXISTS btree_gin;",  # GIN indexes on btree types
    ]
    
    for optimization in optimizations:
        try:
            conn.execute(text(optimization))
            logger.info(f"Applied optimization: {optimization[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to apply optimization: {str(e)}")

# Query optimization hints and patterns
class QueryOptimizations:
    """
    Collection of optimized queries for common patterns
    """
    
    @staticmethod
    def get_user_with_active_accounts(user_id: int):
        """Optimized query to get user with active linked accounts"""
        return text("""
            SELECT u.*, la.*
            FROM users u
            LEFT JOIN linked_accounts la ON u.id = la.user_id AND la.is_active = true
            WHERE u.id = :user_id AND u.is_active = true
        """).bindparam(user_id=user_id)
    
    @staticmethod
    def get_expiring_tokens(minutes_ahead: int = 60):
        """Optimized query for background token refresh job"""
        return text("""
            SELECT la.id, la.user_id, la.email, la.expires_at
            FROM linked_accounts la
            WHERE la.is_active = true
            AND la.needs_reauth = false
            AND la.expires_at <= NOW() + INTERVAL ':minutes minutes'
            AND la.refresh_token_encrypted IS NOT NULL
            ORDER BY la.expires_at ASC
            LIMIT 100
        """).bindparam(minutes=minutes_ahead)
    
    @staticmethod
    def get_user_account_summary(user_id: int):
        """Optimized query for user account summary"""
        return text("""
            SELECT 
                COUNT(*) as total_accounts,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active_accounts,
                COUNT(CASE WHEN needs_reauth = true THEN 1 END) as expired_tokens,
                COUNT(CASE WHEN is_primary = true THEN 1 END) as has_primary
            FROM linked_accounts
            WHERE user_id = :user_id
        """).bindparam(user_id=user_id)
    
    @staticmethod
    def get_daily_audit_summary(date_str: str):
        """Optimized query for daily audit reports"""
        return text("""
            SELECT 
                action,
                status,
                COUNT(*) as count,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT ip_address) as unique_ips
            FROM audit_logs
            WHERE date_trunc('day', created_at) = :date::date
            GROUP BY action, status
            ORDER BY count DESC
        """).bindparam(date=date_str)

# Connection pool optimization
def optimize_connection_pool(engine_config: dict) -> dict:
    """
    Optimize database connection pool settings based on environment
    """
    optimized_config = engine_config.copy()
    
    # Production optimizations
    if engine_config.get('environment') == 'production':
        optimized_config.update({
            'pool_size': 20,  # Base connections
            'max_overflow': 30,  # Burst capacity
            'pool_timeout': 30,  # Connection timeout
            'pool_recycle': 3600,  # Recycle connections every hour
            'pool_pre_ping': True,  # Test connections before use
            'connect_args': {
                'connect_timeout': 10,
                'application_name': 'subscription_tracker_api',
                # Enable connection-level optimizations
                'options': '-c default_transaction_isolation=read_committed'
            }
        })
    
    # Development optimizations
    else:
        optimized_config.update({
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_pre_ping': True
        })
    
    return optimized_config

# Monitoring and maintenance utilities
def get_index_usage_stats(engine):
    """Get PostgreSQL index usage statistics"""
    if engine.dialect.name != 'postgresql':
        return None
    
    query = text("""
        SELECT 
            schemaname,
            tablename,
            indexname,
            idx_tup_read,
            idx_tup_fetch,
            idx_scan as index_scans
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
        ORDER BY idx_scan DESC, idx_tup_read DESC
    """)
    
    with engine.connect() as conn:
        return conn.execute(query).fetchall()

def get_slow_queries(engine, limit: int = 10):
    """Get slow queries from pg_stat_statements"""
    if engine.dialect.name != 'postgresql':
        return None
    
    query = text("""
        SELECT 
            query,
            calls,
            total_time / calls as avg_time_ms,
            total_time,
            rows,
            100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
        FROM pg_stat_statements
        WHERE query NOT LIKE '%pg_stat_statements%'
        ORDER BY total_time DESC
        LIMIT :limit
    """)
    
    with engine.connect() as conn:
        return conn.execute(query.bindparam(limit=limit)).fetchall()