from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://dd:dd@db:5432/dd"
    JWT_SECRET: str = "CHANGE-ME-IN-PRODUCTION"
    CORS_ORIGINS: str = "*"
    ADMIN_EMAIL: str = "quikinnnproducer@gmail.com"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
