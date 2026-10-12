"""로그인 쿠키 서명/검증과 권한 체크.

쿠키 값은 "<user_id>.<HMAC 서명>" 형태라서, 서버의 SECRET_KEY 없이는
다른 사용자 아이디로 바꿔치기할 수 없다.
"""
import base64
import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request
from sqlalchemy import text

from app.config import settings
from app.database import engine

AUTH_COOKIE_NAME = "newsletter_user"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30일

if settings.SECRET_KEY:
    _SECRET = settings.SECRET_KEY.encode()
else:
    # 미설정 시 임시 키 — 서버가 재시작되면 모든 로그인이 풀린다
    _SECRET = secrets.token_bytes(32)
    print("⚠️  SECRET_KEY 미설정 — 임시 키 사용 중 (재시작 시 전체 로그아웃됨)")


def _sign(user_id: str) -> str:
    digest = hmac.new(_SECRET, user_id.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def sign_user_id(user_id: str) -> str:
    return f"{user_id}.{_sign(user_id)}"


def unsign_user_id(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    user_id, sig = value.rsplit(".", 1)
    return user_id if hmac.compare_digest(sig, _sign(user_id)) else None


def set_login_cookie(response, user_id: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=sign_user_id(user_id),
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.SERVER_BASE_URL.startswith("https://"),
    )


def get_user_by_cookie(cookies) -> dict | None:
    user_id = unsign_user_id(cookies.get(AUTH_COOKIE_NAME))
    if not user_id:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM news_users WHERE id = :id"), {"id": user_id}
        ).fetchone()
    return dict(row._mapping) if row else None


def get_current_user(request: Request) -> dict | None:
    return get_user_by_cookie(request.cookies)


# ── FastAPI 의존성 ─────────────────────────────────────────────────────────
def require_admin(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자만 접근할 수 있습니다.")
    return user


def require_admin_or_press(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    if user.get("role") not in ("admin", "press"):
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    return user
