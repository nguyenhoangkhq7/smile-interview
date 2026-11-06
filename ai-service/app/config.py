from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Smile Interview NCKH AI Service"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
