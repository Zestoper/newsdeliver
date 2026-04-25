import secrets
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.database import engine
from app.config import settings

router = APIRouter(prefix="/oauth")

AUTH_COOKIE_NAME = "newsletter_user"


def _upsert_oauth_user(provider: str, oauth_id: str, name: str, email: str | None) -> str:
    """소셜 계정을 DB에서 찾거나 신규 생성 후 user id 반환.
    - 빈 문자열은 NULL로 저장 (empty → None 변환)
    - pw는 소셜 로그인 사용자에게 NULL 저장
    """
    clean_name = (name or "").strip() or f"{provider}사용자"
    
    clean_name = clean_name[:20]
    clean_email = email.strip() if email and email.strip() else None

    with engine.connect() as conn:
        # 1) 동일 소셜 계정 기존 가입 여부
        row = conn.execute(
            text("SELECT id FROM news_users WHERE oauth_provider=:p AND oauth_id=:oid"),
            {"p": provider, "oid": str(oauth_id)}
        ).fetchone()
        if row:
            return row.id

        # 2) 같은 이메일 일반 계정이 있으면 소셜 정보만 연결
        if clean_email:
            row = conn.execute(
                text("SELECT id FROM news_users WHERE email=:email"),
                {"email": clean_email}
            ).fetchone()
            if row:
                conn.execute(
                    text("UPDATE news_users SET oauth_provider=:p, oauth_id=:oid WHERE id=:id"),
                    {"p": provider, "oid": str(oauth_id), "id": row.id}
                )
                conn.commit()
                return row.id

        # 3) 신규 사용자 생성 — ID는 provider prefix + 랜덤 hex (최대 20자)
        prefix = {"kakao": "k_", "naver": "nv_", "google": "g_"}.get(provider, "s_")
        max_tail = 20 - len(prefix)
        for _ in range(5):
            user_id = prefix + secrets.token_hex(10)[:max_tail]
            exists = conn.execute(
                text("SELECT 1 FROM news_users WHERE id=:id"), {"id": user_id}
            ).fetchone()
            if not exists:
                break

        conn.execute(
            text("""
                INSERT INTO news_users (id, name, pw, email, oauth_provider, oauth_id, role)
                VALUES (:id, :name, NULL, :email, :provider, :oauth_id, 'user')
            """),
            {
                "id": user_id,
                "name": clean_name,
                "email": clean_email,
                "provider": provider,
                "oauth_id": str(oauth_id),
            }
        )
        conn.commit()
        return user_id


def _redirect_logged_in(user_id: str) -> RedirectResponse:
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key=AUTH_COOKIE_NAME, value=user_id, httponly=True, samesite="lax")
    return resp


# ── 카카오 ────────────────────────────────────────────────────────────────

@router.get("/kakao")
async def kakao_login():
    if not settings.KAKAO_CLIENT_ID:
        return RedirectResponse(url="/login?social_error=kakao")
    url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={settings.KAKAO_CLIENT_ID}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
        "&response_type=code"
    )
    return RedirectResponse(url=url)


@router.get("/kakao/callback")
async def kakao_callback(code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse(url="/login?social_error=kakao")

    with httpx.Client(timeout=10) as client:
        token_data = {
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_CLIENT_ID,
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
            "code": code,
        }
        if settings.KAKAO_CLIENT_SECRET:
            token_data["client_secret"] = settings.KAKAO_CLIENT_SECRET

        token_res = client.post(
            "https://kauth.kakao.com/oauth/token",
            data=token_data,
        )
        if token_res.status_code != 200:
            return RedirectResponse(url="/login?social_error=kakao")
        access_token = token_res.json().get("access_token", "")

        info_res = client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if info_res.status_code != 200:
            return RedirectResponse(url="/login?social_error=kakao")
        data = info_res.json()

    oauth_id = str(data.get("id", ""))
    account = data.get("kakao_account", {})
    name = (account.get("profile") or {}).get("nickname") or "카카오사용자"
    email = account.get("email")

    user_id = _upsert_oauth_user("kakao", oauth_id, name, email)
    return _redirect_logged_in(user_id)


# ── 네이버 ────────────────────────────────────────────────────────────────

@router.get("/naver")
async def naver_login():
    if not settings.NAVER_OAUTH_CLIENT_ID:
        return RedirectResponse(url="/login?social_error=naver")
    state = secrets.token_hex(8)
    url = (
        "https://nid.naver.com/oauth2.0/authorize"
        f"?client_id={settings.NAVER_OAUTH_CLIENT_ID}"
        f"&redirect_uri={settings.NAVER_OAUTH_REDIRECT_URI}"
        "&response_type=code"
        f"&state={state}"
    )
    return RedirectResponse(url=url)


@router.get("/naver/callback")
async def naver_callback(code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse(url="/login?social_error=naver")

    with httpx.Client(timeout=10) as client:
        token_res = client.post(
            "https://nid.naver.com/oauth2.0/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.NAVER_OAUTH_CLIENT_ID,
                "client_secret": settings.NAVER_OAUTH_CLIENT_SECRET,
                "redirect_uri": settings.NAVER_OAUTH_REDIRECT_URI,
                "code": code,
            },
        )
        if token_res.status_code != 200:
            return RedirectResponse(url="/login?social_error=naver")
        access_token = token_res.json().get("access_token", "")

        info_res = client.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if info_res.status_code != 200:
            return RedirectResponse(url="/login?social_error=naver")
        resp = info_res.json().get("response", {})

    oauth_id = str(resp.get("id", ""))
    name = resp.get("name") or resp.get("nickname") or "네이버사용자"
    email = resp.get("email")

    user_id = _upsert_oauth_user("naver", oauth_id, name, email)
    return _redirect_logged_in(user_id)


# ── 구글 ──────────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    if not settings.GOOGLE_CLIENT_ID:
        return RedirectResponse(url="/login?social_error=google")
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid+email+profile"
        "&access_type=offline"
        "&prompt=select_account"
    )
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse(url="/login?social_error=google")

    with httpx.Client(timeout=10) as client:
        token_res = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "code": code,
            },
        )
        if token_res.status_code != 200:
            return RedirectResponse(url="/login?social_error=google")
        access_token = token_res.json().get("access_token", "")

        info_res = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if info_res.status_code != 200:
            return RedirectResponse(url="/login?social_error=google")
        data = info_res.json()

    oauth_id = str(data.get("id", ""))
    name = data.get("name") or "구글사용자"
    email = data.get("email")

    user_id = _upsert_oauth_user("google", oauth_id, name, email)
    return _redirect_logged_in(user_id)
