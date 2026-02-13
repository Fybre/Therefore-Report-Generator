"""Application configuration."""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# App config file for dynamic settings
APP_CONFIG_FILE = DATA_DIR / "app_config.yaml"


def get_app_config() -> dict:
    """Get application configuration from file."""
    if not APP_CONFIG_FILE.exists():
        return {}
    try:
        import yaml
        with open(APP_CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f) or {}
    except:
        return {}


class Settings(BaseSettings):
    """Application settings."""
    
    # App
    APP_NAME: str = "Therefore Report Generator"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    
    # Application URL (overridden by app_config.yaml if it exists)
    BASE_URL: str = "http://localhost:8000"
    
    # Scheduler
    SCHEDULER_INTERVAL_SECONDS: int = 60
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings."""
    settings = Settings()
    
    # Override BASE_URL from app config if it exists
    app_config = get_app_config()
    if app_config.get('base_url'):
        settings.BASE_URL = app_config['base_url']
    
    return settings
