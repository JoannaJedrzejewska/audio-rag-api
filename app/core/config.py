from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    chromadb_host: str = "localhost"
    chromadb_port: int = 8001
    chroma_collection: str = "transcriptions"

    whisper_model: str = "small"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""

    max_file_size_mb: int = 25

    port: int = 8000
    version: str = "1.0.0"


settings = Settings()
