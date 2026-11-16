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

    # 소셜 로그인 (구글 · 카카오 · 네이버) — app/routers/oauth.py
    # 콜백 주소는 {BACKEND_URL}/oauth/{provider}/callback 로 서버가 직접 만든다.
    BACKEND_URL: str = ""            # 이 서버 주소. 비우면 Render 주소 → SERVER_BASE_URL 순으로 잡는다
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    KAKAO_REST_API_KEY: str = ""
    KAKAO_CLIENT_SECRET: str = ""    # 카카오 콘솔에서 Client Secret 을 '사용'으로 켰을 때만
    NAVER_OAUTH_CLIENT_ID: str = ""
    NAVER_OAUTH_CLIENT_SECRET: str = ""
    # 아래 4개는 예전 소셜 로그인 설정 — 이제 쓰지 않는다. .env 에 남아 있어도 서버가 뜨도록 자리만 둔다.
    # KAKAO_CLIENT_ID 는 KAKAO_REST_API_KEY 가 비었을 때만 대신 쓴다.
    KAKAO_CLIENT_ID: str = ""
    KAKAO_REDIRECT_URI: str = ""
    NAVER_OAUTH_REDIRECT_URI: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    SERVER_BASE_URL: str = "http://127.0.0.1:8000"

    # 로그인 쿠키 서명 키 (운영 환경에서는 반드시 설정)
    SECRET_KEY: str = ""

    # React 프론트엔드 주소 (예: https://newsdeliver.vercel.app)
    # 설정하면 CORS 허용 · 이메일 링크 · 소셜 로그인 · 결제 후 이동이 이 주소를 기준으로 동작한다
    FRONTEND_URL: str = ""

    # 외부 크론(cron-job.org 등)이 /internal/jobs/* 를 호출할 때 쓰는 비밀 키
    # 설정하면 서버 안의 APScheduler 대신 외부 크론 모드로 동작한다 (Render 무료 플랜 슬립 대응)
    CRON_SECRET: str = ""

    GROQ_API_KEY: str = ""
    NEWSAPI_KEY: str = ""


settings = Settings()


def public_base_url() -> str:
    """사용자가 클릭할 링크의 기준 주소 — 프론트엔드가 있으면 프론트엔드, 없으면 서버."""
    return (settings.FRONTEND_URL or settings.SERVER_BASE_URL).rstrip("/")
