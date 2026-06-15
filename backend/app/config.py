"""Application configuration via environment variables."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://helsejournal:helsejournal@localhost:5432/helsejournal"
    DATABASE_URL_SYNC: str = "postgresql://helsejournal:helsejournal@localhost:5432/helsejournal"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT Authentication
    SECRET_KEY: str = "CHANGE-THIS-TO-A-SECURE-RANDOM-KEY-IN-PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    
    # File storage
    UPLOAD_DIR: str = "/data/documents"
    PRIVATE_DIR: str = "/data/private"
    
    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"
    
    # AI / Ollama
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3:8b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # ChromaDB (vector store)
    CHROMA_DIR: str = "/data/chromadb"
    
    # OCR
    TESSERACT_LANG: str = "nor+eng"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
