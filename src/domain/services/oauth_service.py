import json
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from src.core.config import settings
from src.domain.entities.user import User
from src.domain.entities.connected_account import ConnectedAccount
from src.presentation.responses.oauth import GoogleOAuthResponse, ConnectedAccountCreate

class GoogleOAuthService:
    
    def __init__(self, db: Session):
        self.db = db
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]
    
    def create_flow(self, redirect_uri: str) -> Flow:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = redirect_uri
        return flow
    
    def exchange_code_for_tokens(self, authorization_code: str, redirect_uri: str) -> Dict[str, Any]:
        flow = self.create_flow(redirect_uri)
        
        try:
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # Get user info
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            token_data = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expires_at': credentials.expiry.isoformat() if credentials.expiry else None
            }
            
            return {
                'tokens': token_data,
                'user_info': user_info
            }
            
        except Exception as e:
            raise Exception(f"Failed to exchange authorization code: {str(e)}")
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET
        )
        
        try:
            credentials.refresh(Request())
            
            return {
                'access_token': credentials.token,
                'expires_in': 3600,  # Google tokens typically expire in 1 hour
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            raise Exception(f"Failed to refresh token: {str(e)}")
    
    def verify_token_and_get_email(self, access_token: str) -> str:
        credentials = Credentials(token=access_token)
        service = build('oauth2', 'v2', credentials=credentials)
        
        try:
            user_info = service.userinfo().get().execute()
            return user_info.get('email')
        except Exception as e:
            raise Exception(f"Failed to verify token: {str(e)}")

class ConnectedAccountService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_connected_account(self, user_id: int, account_data: ConnectedAccountCreate) -> ConnectedAccount:
        # If this is set as primary, unset other primary accounts
        if account_data.is_primary:
            self.db.query(ConnectedAccount).filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.is_primary == True
            ).update({"is_primary": False})
        
        db_account = ConnectedAccount(
            user_id=user_id,
            email=account_data.email,
            provider=account_data.provider,
            is_primary=account_data.is_primary,
            oauth_tokens=account_data.oauth_tokens
        )
        
        self.db.add(db_account)
        self.db.commit()
        self.db.refresh(db_account)
        return db_account
    
    def get_user_accounts(self, user_id: int) -> list[ConnectedAccount]:
        return self.db.query(ConnectedAccount).filter(
            ConnectedAccount.user_id == user_id
        ).order_by(ConnectedAccount.is_primary.desc(), ConnectedAccount.created_at.asc()).all()
    
    def get_account_by_id(self, account_id: int, user_id: int) -> Optional[ConnectedAccount]:
        return self.db.query(ConnectedAccount).filter(
            ConnectedAccount.id == account_id,
            ConnectedAccount.user_id == user_id
        ).first()
    
    def get_account_by_email(self, email: str, user_id: int) -> Optional[ConnectedAccount]:
        return self.db.query(ConnectedAccount).filter(
            ConnectedAccount.email == email,
            ConnectedAccount.user_id == user_id
        ).first()
    
    def update_account_tokens(self, account_id: int, user_id: int, oauth_tokens: str) -> Optional[ConnectedAccount]:
        account = self.get_account_by_id(account_id, user_id)
        if not account:
            return None
        
        account.oauth_tokens = oauth_tokens
        self.db.commit()
        self.db.refresh(account)
        return account
    
    def update_account_tokens_by_email(self, email: str, user_id: int, oauth_tokens: str) -> Optional[ConnectedAccount]:
        """Update OAuth tokens for an account identified by email and user_id"""
        account = self.get_account_by_email(email, user_id)
        if not account:
            return None
        
        account.oauth_tokens = oauth_tokens
        self.db.commit()
        self.db.refresh(account)
        return account
    
    def set_primary_account(self, account_id: int, user_id: int) -> Optional[ConnectedAccount]:
        # First, unset all primary accounts for this user
        self.db.query(ConnectedAccount).filter(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.is_primary == True
        ).update({"is_primary": False})
        
        # Then set the specified account as primary
        account = self.get_account_by_id(account_id, user_id)
        if not account:
            return None
        
        account.is_primary = True
        self.db.commit()
        self.db.refresh(account)
        return account
    
    def delete_account(self, account_id: int, user_id: int) -> bool:
        account = self.get_account_by_id(account_id, user_id)
        if not account:
            return False
        
        # If deleting primary account, set another account as primary if available
        if account.is_primary:
            other_account = self.db.query(ConnectedAccount).filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.id != account_id
            ).first()
            
            if other_account:
                other_account.is_primary = True
        
        self.db.delete(account)
        self.db.commit()
        return True
    
    def get_primary_account(self, user_id: int) -> Optional[ConnectedAccount]:
        return self.db.query(ConnectedAccount).filter(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.is_primary == True
        ).first()
    
    def account_exists(self, email: str, user_id: int) -> bool:
        return self.db.query(ConnectedAccount).filter(
            ConnectedAccount.email == email,
            ConnectedAccount.user_id == user_id
        ).first() is not None