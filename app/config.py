from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    DB_URL: str = "mysql+pymysql://root:@localhost:3306/newsdelivery"

    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    SMTP_HOST: str = "smtp.naver.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    TOSS_CLIENT_KEY: str = ""
    TOSS_SECRET_KEY: str = ""
    SKIP_PAYMENT: bool = False


settings = Settings()
