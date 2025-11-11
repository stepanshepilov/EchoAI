from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra='ignore')

    PROJECT_NAME: str = "Echo AI"
    API_V1_STR: str = "/api/v1"
    
    OPENAI_API_KEY: str
    
    WHISPER_MODEL: str = "small"
    
    DEEPSEEK_API_BASE: str

    model_name: str = "deepseek-chat"

settings = Settings()
