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
    groq_api_key: Optional[str]
    lm_studio_base_url: str
    lm_studio_model: str
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
        
        lm_studio_base_url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
        lm_studio_model = os.getenv("LM_STUDIO_MODEL", "Llama-Krikri-8B-Instruct-GGUF")
        
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
            lm_studio_base_url=lm_studio_base_url,
            lm_studio_model=lm_studio_model,
            google_credentials_path=google_credentials_path,
            log_level=log_level,
            admin_user_ids=admin_user_ids
        )


# Global config instance
config = Config.from_env()
