"""
Configuration module for Greek Learning Bot.
Loads and validates environment variables.
"""

import os
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class Config:
    """Bot configuration from environment variables."""
    
    # Telegram
    telegram_bot_token: str
    
    # Database
    database_url: str
    
    # AI Services
    groq_api_key: str
    groq_model: str
    google_credentials_path: str
    
    # Logging
    log_level: str
    
    # Admin
    admin_user_ids: List[int]
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        
        # Required variables
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is not set")
        
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY is not set")
            
        groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        
        google_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/google-credentials.json")
        
        # Optional variables
        log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # Parse admin user IDs
        admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
        admin_user_ids = []
        if admin_ids_str:
            try:
                admin_user_ids = [int(uid.strip()) for uid in admin_ids_str.split(",") if uid.strip()]
            except ValueError:
                raise ValueError("ADMIN_USER_IDS must be comma-separated integers")
        
        return cls(
            telegram_bot_token=telegram_bot_token,
            database_url=database_url,
            groq_api_key=groq_api_key,
            groq_model=groq_model,
            google_credentials_path=google_credentials_path,
            log_level=log_level,
            admin_user_ids=admin_user_ids
        )


# Global config instance
config = Config.from_env()
