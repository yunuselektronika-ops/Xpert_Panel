import os
from typing import Optional

class Settings:
    # App settings
    APP_NAME: str = "Xpert Panel"
    APP_SHORT_NAME: str = "Xpert"
    VERSION: str = "1.0.0"
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DOMAIN: str = os.getenv("DOMAIN", "home.turkmendili.ru")
    
    # Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Update settings
    UPDATE_INTERVAL_HOURS: int = int(os.getenv("UPDATE_INTERVAL", "1"))
    
    # Ping settings
    MAX_PING_MS: int = int(os.getenv("MAX_PING_MS", "300"))
    PING_TIMEOUT: int = int(os.getenv("PING_TIMEOUT", "3"))
    MAX_CONFIGS: int = int(os.getenv("MAX_CONFIGS", "100"))
    
    # Data directory
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")

settings = Settings()
