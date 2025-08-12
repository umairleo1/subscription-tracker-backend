import json
import base64
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GmailService:
    
    def __init__(self, oauth_tokens: str, token_update_callback: Optional[Callable[[str], None]] = None):
        self.token_update_callback = token_update_callback
        self.credentials = self._create_credentials(oauth_tokens)
        self.service = self._build_service()
    
    @classmethod
    def create_with_account_persistence(cls, account_id: int, user_id: int, oauth_tokens: str, db_session):
        """
        Create GmailService with automatic token persistence to database
        """
        from src.domain.services.oauth_service import ConnectedAccountService
        
        account_service = ConnectedAccountService(db_session)
        
        def update_tokens(new_tokens: str):
            account_service.update_account_tokens(account_id, user_id, new_tokens)
        
        return cls(oauth_tokens, token_update_callback=update_tokens)
    
    def _create_credentials(self, oauth_tokens: str) -> Credentials:
        token_data = json.loads(oauth_tokens)
        credentials = Credentials(
            token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
            scopes=['https://www.googleapis.com/auth/gmail.readonly']
        )
        return credentials
    
    def _serialize_credentials(self) -> str:
        """Convert credentials back to JSON format for database storage"""
        token_data = {
            'access_token': self.credentials.token,
            'refresh_token': self.credentials.refresh_token,
            'token_uri': self.credentials.token_uri,
            'client_id': self.credentials.client_id,
            'client_secret': self.credentials.client_secret,
            'scopes': self.credentials.scopes,
            'expires_at': self.credentials.expiry.isoformat() if self.credentials.expiry else None
        }
        return json.dumps(token_data)
    
    def _build_service(self):
        if self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
                # Persist the refreshed tokens to database if callback provided
                if self.token_update_callback:
                    updated_tokens = self._serialize_credentials()
                    self.token_update_callback(updated_tokens)
            except Exception as e:
                raise Exception(f"Failed to refresh OAuth token: {str(e)}")
        
        return build('gmail', 'v1', credentials=self.credentials)
    
    def search_subscription_emails(self, days_back: int = 30, max_results: int = 100) -> List[Dict]:
        try:
            # Search for emails that might contain subscription information
            query = self._build_search_query(days_back)
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                email_data = self._fetch_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def _build_search_query(self, days_back: int) -> str:
        # Calculate date for filtering
        start_date = datetime.now() - timedelta(days=days_back)
        date_str = start_date.strftime('%Y/%m/%d')
        
        # Build query for subscription-related emails
        subscription_terms = [
            'subscription', 'billing', 'payment', 'invoice', 
            'receipt', 'renewal', 'recurring', 'charged'
        ]
        
        service_terms = [
            'netflix', 'spotify', 'adobe', 'microsoft', 'apple',
            'amazon', 'google', 'dropbox', 'zoom', 'slack'
        ]
        
        # Combine terms with OR operator
        all_terms = subscription_terms + service_terms
        terms_query = ' OR '.join(all_terms)
        
        # Final query with date filter
        query = f'after:{date_str} ({terms_query})'
        
        return query
    
    def _fetch_email_details(self, message_id: str) -> Optional[Dict]:
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = message['payload'].get('headers', [])
            header_dict = {h['name'].lower(): h['value'] for h in headers}
            
            # Extract body
            body = self._extract_body(message['payload'])
            
            # Parse date
            email_date = self._parse_email_date(header_dict.get('date', ''))
            
            return {
                'id': message_id,
                'sender': header_dict.get('from', ''),
                'subject': header_dict.get('subject', ''),
                'body': body,
                'date': email_date,
                'thread_id': message.get('threadId', ''),
                'labels': message.get('labelIds', [])
            }
            
        except HttpError as error:
            print(f'Error fetching email {message_id}: {error}')
            return None
    
    def _extract_body(self, payload: Dict) -> str:
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body += self._decode_body(part['body']['data'])
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body'] and not body:  # Use HTML if no plain text
                        body += self._decode_body(part['body']['data'])
                elif 'parts' in part:
                    body += self._extract_body(part)
        else:
            if payload['mimeType'] == 'text/plain':
                if 'data' in payload['body']:
                    body = self._decode_body(payload['body']['data'])
        
        return body
    
    def _decode_body(self, encoded_body: str) -> str:
        try:
            decoded_bytes = base64.urlsafe_b64decode(encoded_body)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            print(f'Error decoding email body: {e}')
            return ""
    
    def _parse_email_date(self, date_str: str) -> datetime:
        try:
            # Gmail date format: "Wed, 1 Nov 2023 10:30:00 +0000"
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()
    
    def get_email_by_id(self, email_id: str) -> Optional[Dict]:
        return self._fetch_email_details(email_id)
    
    def search_emails_by_sender(self, sender_domain: str, days_back: int = 90) -> List[Dict]:
        try:
            start_date = datetime.now() - timedelta(days=days_back)
            date_str = start_date.strftime('%Y/%m/%d')
            
            query = f'from:{sender_domain} after:{date_str}'
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                email_data = self._fetch_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            print(f'Error searching emails by sender: {error}')
            return []
    
    def get_thread_emails(self, thread_id: str) -> List[Dict]:
        try:
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            
            emails = []
            for message in thread['messages']:
                email_data = self._fetch_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            print(f'Error fetching thread: {error}')
            return []