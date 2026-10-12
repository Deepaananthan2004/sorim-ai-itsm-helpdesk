from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    app_name: str = "Sorim AI ITSM Helpdesk"
    frontend_origins: str = "http://localhost:5173"
    storage_mode: str = "local"
    local_data_dir: str = "backend/data"
    mongodb_uri: str = ""
    mongodb_database: str = "sorim_itsm"
    servicenow_mode: str = "mock"
    servicenow_instance_url: str = ""
    servicenow_username: str = ""
    servicenow_password: str = ""
    ai_provider: str = "offline"
    huggingface_api_token: str = ""
    huggingface_model: str = "Qwen/Qwen2.5-3B-Instruct"
    embedding_mode: str = "offline"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_relevance_threshold: float = 0.12
    ai_confidence_threshold: float = 0.60
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    @property
    def origins(self):
        return [x.strip() for x in self.frontend_origins.split(",") if x.strip()]

    @property
    def data_path(self):
        p = Path(self.local_data_dir)
        return p if p.is_absolute() else ROOT / p

@lru_cache
def get_settings():
    return Settings()
