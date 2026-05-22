from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    DB_URL: str = "postgresql+psycopg2://postgres:password@localhost:5432/newsdelivery"

    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    SMTP_HOST: str = "smtp.naver.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    TOSS_CLIENT_KEY: str = ""
    TOSS_SECRET_KEY: str = ""
    SKIP_PAYMENT: bool = False

    # 소셜 로그인
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = "http://localhost:8000/oauth/kakao/callback"

    NAVER_OAUTH_CLIENT_ID: str = ""
    NAVER_OAUTH_CLIENT_SECRET: str = ""
    NAVER_OAUTH_REDIRECT_URI: str = "http://localhost:8000/oauth/naver/callback"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/oauth/google/callback"

    SERVER_BASE_URL: str = "http://127.0.0.1:8000"

    GROQ_API_KEY: str = ""
    NEWSAPI_KEY: str = ""


settings = Settings()
