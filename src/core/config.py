from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    class Config:
        env_file = [".env.local", ".env"]  # Priority: .env.local first, then .env
        env_file_encoding = "utf-8"

settings = Settings()