"""
OAuth Token Encryption/Decryption Utilities
Provides secure encryption for storing OAuth tokens at rest
"""
import base64
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from src.core.config.settings import get_settings
import logging

logger = logging.getLogger(__name__)

class TokenEncryption:
    """
    Handles encryption and decryption of OAuth tokens using Fernet (AES 128)
    Uses environment-based encryption key with PBKDF2 key derivation
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._fernet = None
    
    @property
    def fernet(self) -> Fernet:
        """Lazy initialization of Fernet cipher"""
        if self._fernet is None:
            self._fernet = self._get_fernet_cipher()
        return self._fernet
    
    def _get_fernet_cipher(self) -> Fernet:
        """
        Create Fernet cipher from environment key
        Uses PBKDF2 key derivation for security
        """
        # Get encryption key from environment
        encryption_key = self.settings.OAUTH_TOKEN_ENCRYPTION_KEY
        if not encryption_key:
            raise ValueError(
                "OAUTH_TOKEN_ENCRYPTION_KEY environment variable is required. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        
        # Use PBKDF2 to derive a proper Fernet key
        salt = b'oauth_token_salt_2024'  # Fixed salt for consistent key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        return Fernet(key)
    
    def encrypt_token(self, token: str) -> Optional[str]:
        """
        Encrypt an OAuth token
        
        Args:
            token: Raw OAuth token string
            
        Returns:
            Encrypted token as base64 string, or None if token is None/empty
        """
        if not token:
            return None
            
        try:
            # Convert to bytes and encrypt
            token_bytes = token.encode('utf-8')
            encrypted_bytes = self.fernet.encrypt(token_bytes)
            
            # Return as base64 string for database storage
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to encrypt token: {str(e)}")
            raise ValueError(f"Token encryption failed: {str(e)}")
    
    def decrypt_token(self, encrypted_token: str) -> Optional[str]:
        """
        Decrypt an OAuth token
        
        Args:
            encrypted_token: Encrypted token as base64 string
            
        Returns:
            Decrypted token string, or None if encrypted_token is None/empty
        """
        if not encrypted_token:
            return None
            
        try:
            # Decode from base64 and decrypt
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode('utf-8'))
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            
            # Return as string
            return decrypted_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to decrypt token: {str(e)}")
            raise ValueError(f"Token decryption failed: {str(e)}")
    
    def encrypt_oauth_tokens(self, access_token: str = None, refresh_token: str = None, id_token: str = None) -> dict:
        """
        Encrypt multiple OAuth tokens
        
        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token  
            id_token: OAuth ID token
            
        Returns:
            Dictionary with encrypted tokens
        """
        return {
            'access_token_encrypted': self.encrypt_token(access_token),
            'refresh_token_encrypted': self.encrypt_token(refresh_token),
            'id_token_encrypted': self.encrypt_token(id_token)
        }
    
    def decrypt_oauth_tokens(self, access_token_encrypted: str = None, 
                           refresh_token_encrypted: str = None, 
                           id_token_encrypted: str = None) -> dict:
        """
        Decrypt multiple OAuth tokens
        
        Args:
            access_token_encrypted: Encrypted OAuth access token
            refresh_token_encrypted: Encrypted OAuth refresh token
            id_token_encrypted: Encrypted OAuth ID token
            
        Returns:
            Dictionary with decrypted tokens
        """
        return {
            'access_token': self.decrypt_token(access_token_encrypted),
            'refresh_token': self.decrypt_token(refresh_token_encrypted),
            'id_token': self.decrypt_token(id_token_encrypted)
        }

# Global instance for use throughout the application
token_encryption = TokenEncryption()

def encrypt_token(token: str) -> Optional[str]:
    """Convenience function to encrypt a single token"""
    return token_encryption.encrypt_token(token)

def decrypt_token(encrypted_token: str) -> Optional[str]:
    """Convenience function to decrypt a single token"""
    return token_encryption.decrypt_token(encrypted_token)

def encrypt_oauth_tokens(access_token: str = None, refresh_token: str = None, id_token: str = None) -> dict:
    """Convenience function to encrypt OAuth token set"""
    return token_encryption.encrypt_oauth_tokens(access_token, refresh_token, id_token)

def decrypt_oauth_tokens(access_token_encrypted: str = None, 
                        refresh_token_encrypted: str = None, 
                        id_token_encrypted: str = None) -> dict:
    """Convenience function to decrypt OAuth token set"""
    return token_encryption.decrypt_oauth_tokens(access_token_encrypted, refresh_token_encrypted, id_token_encrypted)

# Utility function to generate a new encryption key
def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key"""
    return Fernet.generate_key().decode()

if __name__ == "__main__":
    # For generating encryption keys during setup
    print("Generated encryption key:")
    print(generate_encryption_key())