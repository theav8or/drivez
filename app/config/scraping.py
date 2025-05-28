from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

class ScrapingSettings(BaseSettings):
    # Request settings
    MIN_DELAY_BETWEEN_REQUESTS: float = 1.0  # seconds
    MAX_DELAY_BETWEEN_REQUESTS: float = 3.0  # seconds
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: int = 30  # seconds
    
    # Browser settings
    HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000  # milliseconds
    
    # Yad2 specific settings
    YAD2_BASE_URL: str = "https://www.yad2.co.il"
    YAD2_SEARCH_PATH: str = "/vehicles/cars"
    
    # Proxy settings (if needed)
    USE_PROXY: bool = False
    PROXY_SERVER: Optional[str] = None
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 30
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # Cache settings
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # 1 hour
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = "scraping.log"
    
    class Config:
        env_prefix = "SCRAPING_"
        case_sensitive = False

# Create a settings instance
settings = ScrapingSettings()