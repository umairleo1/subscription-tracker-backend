"""
Authentication utilities
TODO: Implement proper authentication in production
"""
import uuid
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.domain.entities.user import User


async def get_current_active_user(
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current active user
    TODO: Replace with proper JWT/session-based authentication
    For development purposes, returns the first active user
    """
    user = db.query(User).filter(User.is_active == True).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active users found. Please create a user first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user