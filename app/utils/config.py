#services/backend-auth/app/utils/config.py
from pydantic_settings import BaseSettings
from typing import List
from urllib.parse import quote_plus
from pathlib import Path

class Settings(BaseSettings):
    # Database settings
    DB_PASSWORD: str
    DB_NAME: str
    DB_HOST: str
    DB_PORT: str
    DB_USER: str

    # JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 

    # Other settings
    DEBUG: bool = True 
    ALLOWED_HOSTS: str = "*"

    # OpenAI settings
    OPENAI_API_KEY: str

    # Service URLs  
    SERVICE_KEY_SALT: str  
    NARRATIVE_SERVICE_URL: str 
    CHATBOT_SERVICE_URL: str  
    METRIC_DISCOVERY_SERVICE_URL: str  
    METRICS_SERVICE_URL: str  
    ORGANIZATIONS_SERVICE_URL: str  
    DATA_SOURCE_SERVICE_URL: str  


    @property
    def DATABASE_URL(self):
        url = f"postgresql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?sslmode=require"
        return url

    @property
    def ALLOWED_HOSTS_LIST(self) -> List[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(',')]

    class Config:
        env_file = "../../../../.env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from environment variables

settings = Settings()