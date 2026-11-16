"""소셜 로그인 (구글 · 카카오) — OAuth2 Authorization Code Flow

흐름
  1. 프론트 버튼 → GET /oauth/{provider}/login → 구글/카카오 로그인 화면으로 이동
  2. 로그인 후 구글/카카오가 GET /oauth/{provider}/callback?code=...&state=... 로 돌려보냄
  3. code 를 구글/카카오 access token 으로 바꾸고, 그 토큰으로 사용자 정보(id · 이메일 · 이름) 조회
  4. 연결된 계정이 있으면 그 계정, 없으면 같은 이메일 계정에 연결, 그것도 없으면 새로 가입
  5. 기존 이메일 로그인과 똑같은 자체 토큰을 만들어 프론트 /auth/callback#token=... 으로 보냄
     (실패하면 /login?oauth_error=... 로 보내 화면에 안내 문구를 띄운다)

필요한 환경변수
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  KAKAO_REST_API_KEY, KAKAO_CLIENT_SECRET(카카오 콘솔에서 켰을 때만)
  BACKEND_URL   — 이 서버 주소 (콜백 주소를 만들 때 사용. 비우면 Render 주소 → SERVER_BASE_URL 순으로 잡는다)
  FRONTEND_URL  — 로그인 후 돌아갈 프론트 주소

구글/카카오 콘솔에 등록할 Redirect URI
  {BACKEND_URL}/oauth/google/callback
  {BACKEND_URL}/oauth/kakao/callback

네이버(NAVER_OAUTH_CLIENT_ID · NAVER_OAUTH_CLIENT_SECRET)도 같은 방식으로 동작한다.
프론트 주소(FRONTEND_URL)가 없으면 예전처럼 로그인 쿠키를 심고 서버가 그리는 첫 화면으로 보낸다.
"""
import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.auth import _SECRET, issue_token, set_login_cookie
from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth")

BACKEND_URL  = (settings.BACKEND_URL or os.getenv("RENDER_EXTERNAL_URL") or settings.SERVER_BASE_URL).rstrip("/")
FRONTEND_URL = settings.FRONTEND_URL.rstrip("/")
CALLBACK_PREFIX = "/oauth"
STATE_SECRET = _SECRET  # 로그인 쿠키·토큰과 같은 서버 비밀키

GOOGLE_CLIENT_ID     = settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
KAKAO_REST_API_KEY   = settings.KAKAO_REST_API_KEY or settings.KAKAO_CLIENT_ID
KAKAO_CLIENT_SECRET  = settings.KAKAO_CLIENT_SECRET
NAVER_CLIENT_ID      = settings.NAVER_OAUTH_CLIENT_ID
NAVER_CLIENT_SECRET  = settings.NAVER_OAUTH_CLIENT_SECRET


def _fail(message: str) -> RedirectResponse:
    """실패하면 로그인 화면으로 돌려보내고 화면에 안내 문구를 띄운다."""
    return RedirectResponse(f"{FRONTEND_URL}/login?oauth_error={quote(message)}", status_code=303)

PROVIDERS = {
    "google": {
        "label":         "구글",
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":     "https://oauth2.googleapis.com/token",
        "userinfo_url":  "https://openidconnect.googleapis.com/v1/userinfo",
        "scope":         "openid email profile",
    },
    "kakao": {
        "label":         "카카오",
        "client_id":     KAKAO_REST_API_KEY,
        "client_secret": KAKAO_CLIENT_SECRET,  # 콘솔에서 '사용'으로 켰을 때만 필요
        "authorize_url": "https://kauth.kakao.com/oauth/authorize",
        "token_url":     "https://kauth.kakao.com/oauth/token",
        "userinfo_url":  "https://kapi.kakao.com/v2/user/me",
        "scope":         "profile_nickname account_email",
    },
    # 네이버는 예전부터 있던 로그인이라 같은 방식으로 함께 둔다 (키가 없으면 버튼이 보이지 않는다)
    "naver": {
        "label":         "네이버",
        "client_id":     NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "authorize_url": "https://nid.naver.com/oauth2.0/authorize",
        "token_url":     "https://nid.naver.com/oauth2.0/token",
        "userinfo_url":  "https://openapi.naver.com/v1/nid/me",
        "scope":         "",
    },
}


def _callback_url(provider: str) -> str:
    # 구글/카카오 콘솔에 등록한 Redirect URI 와 글자 하나까지 같아야 한다
    return f"{BACKEND_URL}{CALLBACK_PREFIX}/{provider}/callback"


# ── CSRF 방지용 state ────────────────────────────────────────────────────────
# 프론트(Vercel)와 백엔드(Render) 도메인이 달라 쿠키 세션을 쓰기 어렵다.
# 그래서 서버 비밀키로 서명한 10분짜리 값을 state 로 보내고, 돌아올 때 서명을 검증한다.
# → 우리 서버가 시작하지 않은 로그인 요청(위조)은 콜백에서 거절된다.
def _sign(message: str) -> str:
    digest = hmac.new(STATE_SECRET, message.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _make_state(provider: str) -> str:
    exp = str(int(time.time()) + 600)
    nonce = secrets.token_hex(8)
    return f"{exp}.{nonce}.{_sign(f'{provider}.{exp}.{nonce}')}"


def _state_ok(state: str, provider: str) -> bool:
    parts = (state or "").split(".")
    if len(parts) != 3 or not parts[0].isdigit() or int(parts[0]) < time.time():
        return False
    exp, nonce, sig = parts
    return hmac.compare_digest(sig, _sign(f"{provider}.{exp}.{nonce}"))


# ── 구글/카카오/네이버 사용자 정보 → 공통 형식 ─────────────────────────────────────
def _normalize(provider: str, raw: dict) -> dict:
    if provider == "google":
        return {
            "provider_id":    str(raw["sub"]),
            "email":          (raw.get("email") or "").strip().lower() or None,
            "email_verified": bool(raw.get("email_verified")),
            "name":           (raw.get("name") or "").strip(),
        }
    if provider == "naver":
        resp = raw.get("response") or {}
        email = (resp.get("email") or "").strip().lower() or None
        return {
            "provider_id":    str(resp["id"]),
            "email":          email,
            "email_verified": bool(email),  # 네이버는 인증 여부를 따로 주지 않는다 (예전 동작 유지)
            "name":           (resp.get("name") or resp.get("nickname") or "").strip(),
        }
    account = raw.get("kakao_account") or {}
    return {
        "provider_id":    str(raw["id"]),
        # 사용자가 이메일 제공에 동의하지 않으면 없을 수 있다
        "email":          (account.get("email") or "").strip().lower() or None,
        "email_verified": bool(account.get("is_email_valid") and account.get("is_email_verified")),
        "name":           ((account.get("profile") or {}).get("nickname") or "").strip(),
    }


def _authorize_url(provider: str, cfg: dict) -> str:
    params = {
        "client_id":     cfg["client_id"],
        "redirect_uri":  _callback_url(provider),
        "response_type": "code",
        "state":         _make_state(provider),
    }
    if cfg["scope"]:
        params["scope"] = cfg["scope"]
    if provider == "google":
        params["prompt"] = "select_account"  # 여러 구글 계정 중 고를 수 있게
    return f"{cfg['authorize_url']}?{urlencode(params)}"


def _token_form(provider: str, cfg: dict, code: str) -> dict:
    data = {
        "grant_type":   "authorization_code",
        "client_id":    cfg["client_id"],
        "redirect_uri": _callback_url(provider),
        "code":         code,
    }
    if cfg["client_secret"]:
        data["client_secret"] = cfg["client_secret"]
    return data


def _log_fetch_error(provider: str, e: Exception) -> None:
    body = getattr(getattr(e, "response", None), "text", "")[:300]
    logger.error("[oauth] %s 토큰/사용자 조회 실패: %s: %s %s", provider, type(e).__name__, e, body)


def _fetch_profile(provider: str, cfg: dict, code: str) -> dict:
    """code → access token → 사용자 정보. 실패하면 예외."""
    with httpx.Client(timeout=10) as client:
        token_res = client.post(cfg["token_url"], data=_token_form(provider, cfg, code),
                                headers={"Accept": "application/json"})
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]
        me_res = client.get(cfg["userinfo_url"], headers={"Authorization": f"Bearer {access_token}"})
        me_res.raise_for_status()
        return _normalize(provider, me_res.json())


def enabled_providers() -> dict:
    """키가 설정된 로그인 방식만 버튼을 보여주기 위한 목록."""
    return {name: bool(cfg["client_id"]) for name, cfg in PROVIDERS.items()}


def _new_user_id(conn, provider: str) -> str:
    # 아이디는 provider 접두사 + 랜덤 hex (최대 20자)
    prefix = {"kakao": "k_", "naver": "nv_", "google": "g_"}.get(provider, "s_")
    while True:
        user_id = prefix + secrets.token_hex(10)[:20 - len(prefix)]
        if not conn.execute(text("SELECT 1 FROM news_users WHERE id = :id"), {"id": user_id}).fetchone():
            return user_id


def _find_or_create_user(provider: str, info: dict) -> str:
    """소셜 계정에 해당하는 회원 아이디를 돌려준다 (없으면 새로 가입)."""
    with engine.connect() as conn:
        # 1) 이미 연결된 소셜 계정
        row = conn.execute(
            text("SELECT id FROM news_users WHERE oauth_provider = :p AND oauth_id = :oid"),
            {"p": provider, "oid": info["provider_id"]},
        ).fetchone()
        if row:
            return row.id

        # 2) 같은 이메일로 가입한 계정이 있으면 그 계정으로 로그인
        #    구글/카카오가 '인증된 이메일'이라고 확인해 준 경우만 — 아니면 남의 계정에 붙을 수 있다
        same_email = None
        if info["email"]:
            same_email = conn.execute(
                text("SELECT id, oauth_provider FROM news_users WHERE LOWER(email) = :email"),
                {"email": info["email"]},
            ).fetchone()
        if same_email and info["email_verified"]:
            # 회원 한 명에 소셜 계정은 하나만 기록된다. 이미 다른 소셜이 연결돼 있으면 덮어쓰지 않는다
            # (다음에도 이메일이 같아서 이 계정으로 들어온다)
            if not same_email.oauth_provider:
                conn.execute(
                    text("UPDATE news_users SET oauth_provider = :p, oauth_id = :oid WHERE id = :id"),
                    {"p": provider, "oid": info["provider_id"], "id": same_email.id},
                )
                conn.commit()
            return same_email.id

        # 3) 없으면 새로 가입 — 비밀번호(pw)는 NULL 이라 비밀번호로는 로그인할 수 없다
        user_id = _new_user_id(conn, provider)
        conn.execute(
            text("""
                INSERT INTO news_users (id, name, pw, email, oauth_provider, oauth_id, role)
                VALUES (:id, :name, NULL, :email, :provider, :oauth_id, 'user')
            """),
            {
                "id": user_id,
                "name": (info["name"] or f"{PROVIDERS[provider]['label']}사용자")[:20],
                # email 은 중복될 수 없다 — 이미 다른 계정이 쓰는 주소(또는 50자 초과)면 비워 둔다
                "email": info["email"] if info["email"] and not same_email and len(info["email"]) <= 50 else None,
                "provider": provider,
                "oauth_id": info["provider_id"],
            },
        )
        conn.commit()
        return user_id


def _redirect_logged_in(user_id: str) -> RedirectResponse:
    # React 프론트엔드가 있으면 토큰을 URL 해시(#)로 넘긴다 — 해시는 서버 로그에 남지 않는다
    if FRONTEND_URL:
        return RedirectResponse(f"{FRONTEND_URL}/auth/callback#token={issue_token(user_id)}", status_code=303)
    resp = RedirectResponse(url="/", status_code=303)
    set_login_cookie(resp, user_id)
    return resp


@router.get("/{provider}")          # 예전 주소 (/oauth/kakao) — 서버가 그리는 로그인 화면이 쓴다
@router.get("/{provider}/login")
def social_login(provider: str):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return _fail("지원하지 않는 로그인 방식입니다")
    if not cfg["client_id"]:
        return _fail(f"{cfg['label']} 로그인이 아직 설정되지 않았습니다")
    return RedirectResponse(_authorize_url(provider, cfg))


@router.get("/{provider}/callback")
def social_callback(provider: str, code: str = "", state: str = "", error: str = ""):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return _fail("지원하지 않는 로그인 방식입니다")
    if error or not code:
        return _fail("로그인이 취소되었습니다")
    if not _state_ok(state, provider):
        return _fail("로그인 요청이 만료되었습니다. 다시 시도해주세요")

    try:
        info = _fetch_profile(provider, cfg, code)
    except Exception as e:
        _log_fetch_error(provider, e)
        return _fail("소셜 로그인에 실패했습니다. 잠시 후 다시 시도해주세요")

    try:
        user_id = _find_or_create_user(provider, info)
    except Exception as e:
        logger.error("[oauth] %s 계정 처리 실패: %s: %s", provider, type(e).__name__, e)
        return _fail("계정 처리 중 오류가 발생했습니다")

    return _redirect_logged_in(user_id)
