import os  
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")

class Settings(BaseSettings):
    DATABASE_URL: str 
    SECRET_KEY: str 
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int 
    REFRESH_TOKEN_EXPIRE_DAYS: int 
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    REDIS_URL: str

    model_config = SettingsConfigDict(env_file=ENV_PATH)
    
settings = Settings()
