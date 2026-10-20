"""아이디 찾기 · 비밀번호 재설정.

보안 원칙
- 입력한 이메일·아이디가 있든 없든 화면 응답은 똑같다 (가입 여부를 알아낼 수 없게)
- 아이디는 화면이 아니라 가입 이메일로만 보낸다
- 재설정 링크 토큰은 원문을 메일로만 보내고 DB에는 SHA-256 해시만 저장한다 (DB가 새도 링크를 만들 수 없음)
- 링크는 30분 뒤 만료되고 한 번 쓰면 끝난다 · 새 링크를 요청하면 이전 링크는 무효
- 같은 이메일·아이디로 15분에 3번까지만 요청할 수 있다 (메일 폭탄 방지)
"""
import hashlib
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database import engine
from app.services.email import send_account_email_async
from app.services.passwords import hash_password

RESET_TTL = timedelta(minutes=30)
_RATE_WINDOW = 15 * 60
_RATE_MAX = 3
_rate: dict[str, list[float]] = {}
_rate_lock = threading.Lock()

SOCIAL_LABEL = {"kakao": "카카오", "naver": "네이버", "google": "구글"}


def _allowed(key: str) -> bool:
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate.get(key, []) if now - t < _RATE_WINDOW]
        if len(hits) >= _RATE_MAX:
            _rate[key] = hits
            return False
        hits.append(now)
        _rate[key] = hits
        return True


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # DB에는 UTC 기준 naive 시각으로 저장


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ensure_table(conn) -> None:
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS password_resets ("
        " token_hash VARCHAR(64) PRIMARY KEY,"
        " user_id VARCHAR(100) NOT NULL,"
        " expires_at TIMESTAMP NOT NULL,"
        " used SMALLINT DEFAULT 0,"
        " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    ))


def _mask(user_id: str) -> str:
    return user_id[:3] + "*" * max(2, len(user_id) - 3) if len(user_id) > 3 else user_id[0] + "**"


def request_find_id(email: str, base_url: str) -> None:
    """가입 이메일로 아이디를 보낸다. 결과는 호출한 쪽에 알려주지 않는다."""
    email = (email or "").strip()
    if not email or not _allowed(f"id:{email.lower()}"):
        return
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, oauth_provider FROM news_users WHERE LOWER(email) = LOWER(:email)"),
            {"email": email},
        ).fetchall()
    if not rows:
        return
    lines = []
    for r in rows:
        if r.oauth_provider:
            lines.append(f"<b>{SOCIAL_LABEL.get(r.oauth_provider, r.oauth_provider)} 로그인</b>으로 가입한 계정이 있어요.")
        else:
            lines.append(f"아이디: <b>{r.id}</b>")
    send_account_email_async(
        email, "[News Delivery] 아이디 안내", "아이디 안내",
        "요청하신 계정 정보입니다.<br><br>" + "<br>".join(lines),
        "로그인하러 가기", f"{base_url.rstrip('/')}/login",
    )


def request_password_reset(user_id: str, email: str, base_url: str) -> None:
    """아이디와 이메일이 맞으면 재설정 링크를 메일로 보낸다. 결과는 호출한 쪽에 알려주지 않는다."""
    user_id, email = (user_id or "").strip(), (email or "").strip()
    if not user_id or not email or not _allowed(f"pw:{user_id.lower()}"):
        return
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, pw, oauth_provider FROM news_users WHERE id = :id AND LOWER(email) = LOWER(:email)"),
            {"id": user_id, "email": email},
        ).fetchone()
        if not row:
            return
        if row.oauth_provider and not row.pw:
            send_account_email_async(
                email, "[News Delivery] 비밀번호 재설정 안내", "소셜 로그인 계정이에요",
                f"이 계정은 <b>{SOCIAL_LABEL.get(row.oauth_provider, row.oauth_provider)} 로그인</b>으로 가입해서 "
                "비밀번호가 없어요.<br>로그인 화면에서 소셜 로그인 버튼으로 들어와 주세요.",
                "로그인하러 가기", f"{base_url.rstrip('/')}/login",
            )
            return
        _ensure_table(conn)
        conn.execute(text("DELETE FROM password_resets WHERE user_id = :uid OR expires_at < :now"),
                     {"uid": row.id, "now": _now()})
        token = secrets.token_urlsafe(32)
        conn.execute(
            text("INSERT INTO password_resets (token_hash, user_id, expires_at) VALUES (:h, :uid, :exp)"),
            {"h": _token_hash(token), "uid": row.id, "exp": _now() + RESET_TTL},
        )
        conn.commit()
    send_account_email_async(
        email, "[News Delivery] 비밀번호 재설정", "비밀번호 재설정",
        f"<b>{_mask(row.id)}</b> 계정의 비밀번호 재설정을 요청하셨어요.<br>"
        "아래 버튼을 눌러 새 비밀번호를 정해 주세요.<br>링크는 <b>30분 동안 한 번만</b> 쓸 수 있어요.",
        "비밀번호 재설정하기", f"{base_url.rstrip('/')}/reset-password?token={token}",
    )


def check_reset_token(token: str) -> bool:
    with engine.connect() as conn:
        _ensure_table(conn)
        conn.commit()
        row = conn.execute(
            text("SELECT 1 FROM password_resets WHERE token_hash = :h AND used = 0 AND expires_at > :now"),
            {"h": _token_hash(token or ""), "now": _now()},
        ).fetchone()
    return row is not None


def reset_password(token: str, new_password: str) -> bool:
    """토큰이 유효하면 비밀번호를 바꾸고 True. 만료·사용됨·없음이면 False."""
    with engine.connect() as conn:
        _ensure_table(conn)
        row = conn.execute(
            text("SELECT user_id FROM password_resets WHERE token_hash = :h AND used = 0 AND expires_at > :now"),
            {"h": _token_hash(token or ""), "now": _now()},
        ).fetchone()
        if not row:
            conn.commit()
            return False
        conn.execute(text("UPDATE news_users SET pw = :pw WHERE id = :id"),
                     {"pw": hash_password(new_password), "id": row.user_id})
        conn.execute(text("DELETE FROM password_resets WHERE user_id = :id"), {"id": row.user_id})
        conn.commit()
    return True
