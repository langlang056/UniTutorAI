"""Application configuration management."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys (与老项目相同的命名)
    llama_cloud_api_key: str = ""  # 可选,如果为空则使用 PyPDF2
    google_api_key: str = ""  # Google Gemini API Key (与老项目相同)
    google_model: str = "gemini-2.0-flash-exp"  # Gemini 模型
    
    # 默认 API Key (用于未配置用户,从环境变量读取,不暴露给前端)
    default_api_key: str = ""  # 默认的免费层级 API Key
    default_model: str = "gemini-2.5-flash"  # 默认使用的模型

    # Paths
    upload_dir: str = "uploads"
    temp_dir: str = "temp"
    database_url: str = "sqlite+aiosqlite:///./unitutor.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # Processing
    max_file_size_mb: int = 50
    supported_formats: list[str] = [".pdf"]

    # LLM Settings
    max_tokens: int = 50000
    temperature: float = 0.7

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
