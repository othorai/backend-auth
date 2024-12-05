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

    # AWS settings
    AWS_REGION: str = "eu-north-1"
    AWS_ACCOUNT_ID: str = "533267025675"
    AWS_ACCESS_KEY_ID: str  
    AWS_SECRET_ACCESS_KEY: str
    APP_NAME: str = "backend-authorization-gateway"
    CLUSTER_NAME: str = "backend-authorization-gateway-cluster"
    SERVICE_NAME: str = "backend-authorization-gateway-service"

    # ECS Configuration
    ECS_CPU: str = "256"
    ECS_MEMORY: str = "512"
    ECS_CONTAINER_PORT: str = "8000"

    # VPC Configuration
    VPC_ID: str  
    VPC_SUBNET_1: str  
    VPC_SUBNET_2: str  
    SECURITY_GROUP: str  

    # Service URLs
    AUTH_SERVICE_NAME: str  
    SERVICE_KEY_SALT: str  
    NARRATIVE_SERVICE_URL: str  
    CHATBOT_SERVICE_URL: str  
    METRIC_DISCOVERY_SERVICE_URL: str  
    METRICS_SERVICE_URL: str  
    ORGANIZATIONS_SERVICE_URL: str  
    DATA_SOURCE_SERVICE_URL: str  

    # Load Balancer ARNs
    TARGET_GROUP_ARN: str  
    ALB_ARN: str  
    LISTENER_ARN: str  

    @property
    def DATABASE_URL(self):
        url = f"postgresql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?sslmode=require"
        return url

    @property
    def ALLOWED_HOSTS_LIST(self) -> List[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(',')]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from environment variables

settings = Settings()