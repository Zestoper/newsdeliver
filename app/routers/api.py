"""React 프론트엔드용 JSON API (/api/v1).

기존 서버 렌더링 페이지(pages.py)가 템플릿에 넘기던 데이터를 그대로 JSON으로 돌려준다.
로그인은 쿠키 대신 Bearer 토큰(app.auth.issue_token)을 쓴다.

좋아요·북마크·댓글·신고·카테고리 구독·채팅처럼 원래 JSON을 돌려주던 엔드포인트는
pages.py / chat.py 에 그대로 두고, get_current_user 가 Bearer 토큰도 읽도록 바꿔서 함께 쓴다.
"""
import base64
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import get_current_user, issue_token
from app.config import public_base_url, settings
from app.database import engine
from app.routers.pages import (
    _AGE_GROUP_CONFIG,
    _AGE_PAGE_SIZE,
    _NEWS_PAGE_SIZE,
    _do_verify,
)
from app.services.email import send_verify_email
from app.services.store import (
    add_subscription,
    add_user,
    get_user,
    is_duplicate_subscription,
    is_duplicate_user,
)

router = APIRouter(prefix="/api/v1", tags=["frontend"])


# ── 공통 ──────────────────────────────────────────────────────────────────

_PUBLIC_USER_FIELDS = ("id", "name", "email", "tel", "role", "birth", "oauth_provider", "press_approved")


def _public_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {k: user.get(k) for k in _PUBLIC_USER_FIELDS}


def _require_user(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user


def _rows(conn, sql: str, params: dict | None = None) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params or {})]


# ── 인증 ──────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    user_id: str
    password: str


class SignupBody(BaseModel):
    name: str
    birth: str
    user_id: str
    password: str
    email: str
    phone: str
    press: bool = False  # 언론사 회원가입이면 true


@router.get("/auth/providers")
def auth_providers():
    return {
        "kakao": bool(settings.KAKAO_CLIENT_ID),
        "naver": bool(settings.NAVER_OAUTH_CLIENT_ID),
        "google": bool(settings.GOOGLE_CLIENT_ID),
    }


@router.post("/auth/login")
def login(body: LoginBody):
    user = get_user(user_id=body.user_id, password=body.password)
    if not user:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    press_notice = False
    if user.get("role") == "press" and user.get("press_approved") and not user.get("press_notified"):
        with engine.connect() as conn:
            conn.execute(text("UPDATE news_users SET press_notified = 1 WHERE id = :id"), {"id": body.user_id})
            conn.commit()
        press_notice = True
    return {"token": issue_token(user["id"]), "user": _public_user(user), "press_notice": press_notice}


@router.get("/auth/me")
def me(request: Request):
    return {"user": _public_user(_require_user(request))}


@router.post("/auth/signup")
def signup(body: SignupBody):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상으로 입력해주세요.")
    dup = is_duplicate_user(user_id=body.user_id, email=body.email)
    if dup["id"] and dup["email"]:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디와 이메일입니다. 둘 다 변경해주세요.")
    if dup["id"]:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다. 다른 아이디를 입력해주세요.")
    if dup["email"]:
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다. 다른 이메일을 입력해주세요.")
    if body.press:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO news_users (id, name, birth, pw, email, tel, role)
                    VALUES (:id, :name, :birth, :pw, :email, :tel, 'press')
                """),
                {"id": body.user_id, "name": body.name, "birth": body.birth,
                 "pw": body.password, "email": body.email, "tel": body.phone},
            )
            conn.commit()
    else:
        add_user({
            "name": body.name, "birth": body.birth, "user_id": body.user_id,
            "password": body.password, "email": body.email, "phone": body.phone,
        })
    return {"success": True}


# ── 메인 ──────────────────────────────────────────────────────────────────

@router.get("/home")
def home():
    with engine.connect() as conn:
        news_items = _rows(conn, """
            SELECT n.id, n.title, n.image_url, LEFT(n.content, 300) AS content, n.created_at,
                   c.name AS category_name
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE n.status = 'published' AND COALESCE(n.is_global, 0) = 0
            ORDER BY n.created_at DESC
            LIMIT 20
        """)
        top_commented = _rows(conn, """
            SELECT n.id, n.title, n.created_at, c.name AS category_name,
                   COUNT(nc.id) AS comment_count
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            LEFT JOIN news_comments nc ON n.id = nc.news_id
            WHERE n.status = 'published'
            GROUP BY n.id, n.title, n.created_at, c.name
            ORDER BY comment_count DESC
            LIMIT 5
        """)
        top_liked = _rows(conn, """
            SELECT n.id, n.title, n.created_at, c.name AS category_name,
                   COUNT(nl.id) AS like_count
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            LEFT JOIN news_likes nl ON n.id = nl.news_id
            WHERE n.status = 'published'
            GROUP BY n.id, n.title, n.created_at, c.name
            ORDER BY like_count DESC
            LIMIT 5
        """)
        top_viewed = _rows(conn, """
            SELECT n.id, n.title, n.view_count, n.created_at, c.name AS category_name
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE n.status = 'published'
            ORDER BY COALESCE(n.view_count, 0) DESC
            LIMIT 10
        """)
        big5_news = []
        for src in ['조선일보', '중앙일보', '동아일보', '한겨레', '연합뉴스', '경향신문']:
            row = conn.execute(text("""
                SELECT n.id, n.title, n.image_url, n.source, n.created_at, c.name AS category_name
                FROM news n
                LEFT JOIN categories c ON n.category_id = c.id
                WHERE n.status = 'published' AND n.source = :src
                ORDER BY COALESCE(n.view_count, 0) DESC LIMIT 1
            """), {"src": src}).fetchone()
            if row:
                big5_news.append(dict(row._mapping))
    return {
        "news_items": news_items,
        "top_commented": top_commented,
        "top_liked": top_liked,
        "top_viewed": top_viewed,
        "big5_news": big5_news,
        "today": date.today().strftime("%Y년 %m월 %d일"),
    }


# ── 뉴스 목록 · 상세 · 검색 ───────────────────────────────────────────────

def _news_page(base: str, category: str, page: int, categories: list[dict]) -> dict:
    page = max(1, page)
    offset = (page - 1) * _NEWS_PAGE_SIZE
    params: dict = {"limit": _NEWS_PAGE_SIZE, "offset": offset}
    where = base
    if category:
        where += " AND c.name = :category"
        params["category"] = category
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM news n LEFT JOIN categories c ON n.category_id = c.id WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        ).scalar() or 0
        items = _rows(conn, f"""
            SELECT n.id, n.title, n.image_url, LEFT(n.content, 300) AS content, n.source,
                   n.created_at, n.view_count, c.name AS category_name
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE {where}
            ORDER BY n.created_at DESC LIMIT :limit OFFSET :offset
        """, params)
    return {
        "news_items": items,
        "categories": categories,
        "selected_category": category,
        "page": page,
        "total_pages": max(1, (total + _NEWS_PAGE_SIZE - 1) // _NEWS_PAGE_SIZE),
    }


@router.get("/news")
def news_list(category: str = "", page: int = 1):
    with engine.connect() as conn:
        categories = _rows(conn, """
            SELECT DISTINCT c.* FROM categories c
            JOIN news n ON n.category_id = c.id
            WHERE COALESCE(n.is_global, 0) = 0
        """)
    return _news_page("n.status = 'published' AND COALESCE(n.is_global, 0) = 0", category, page, categories)


@router.get("/global-news")
def global_news_list(category: str = "", page: int = 1):
    with engine.connect() as conn:
        categories = _rows(conn, """
            SELECT * FROM categories WHERE name IN
            ('정치','경제','IT','문화','스포츠','예술','연예','국제','사회')
            ORDER BY array_position(ARRAY['정치','경제','IT','문화','스포츠','예술','연예','국제','사회']::text[], name)
        """)
    return _news_page("n.status = 'published' AND n.is_global = 1", category, page, categories)


@router.get("/news/{news_id}")
def news_detail(news_id: int, request: Request):
    user = get_current_user(request)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT n.*, c.name AS category_name FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE n.id = :id
        """), {"id": news_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
        news = dict(row._mapping)
        conn.execute(
            text("UPDATE news SET view_count = COALESCE(view_count, 0) + 1 WHERE id = :id"),
            {"id": news_id},
        )
        conn.commit()
        news["view_count"] = (news.get("view_count") or 0) + 1
        like_count = conn.execute(
            text("SELECT COUNT(*) FROM news_likes WHERE news_id = :id"), {"id": news_id}
        ).scalar()
        liked = bookmarked = subscribed = False
        if user:
            p = {"news_id": news_id, "user_id": user["id"]}
            liked = conn.execute(text(
                "SELECT 1 FROM news_likes WHERE news_id = :news_id AND user_id = :user_id"), p
            ).fetchone() is not None
            bookmarked = conn.execute(text(
                "SELECT 1 FROM bookmarks WHERE news_id = :news_id AND user_id = :user_id"), p
            ).fetchone() is not None
            sub = conn.execute(
                text("SELECT is_active FROM subscriptions WHERE user_id = :user_id"), {"user_id": user["id"]}
            ).fetchone()
            subscribed = bool(sub and sub.is_active)
        related = []
        if news.get("category_id"):
            related = _rows(conn, """
                SELECT n.id, n.title, n.image_url, n.view_count, n.created_at, c.name AS category_name
                FROM news n
                LEFT JOIN categories c ON n.category_id = c.id
                WHERE n.status = 'published' AND n.category_id = :cat_id AND n.id != :news_id
                ORDER BY COALESCE(n.view_count, 0) DESC
                LIMIT 4
            """, {"cat_id": news["category_id"], "news_id": news_id})
    can_delete = bool(user and (user["id"] == news.get("author_id") or user.get("role") == "admin"))
    return {
        "news": news,
        "like_count": like_count,
        "liked": liked,
        "bookmarked": bookmarked,
        "subscribed": subscribed,
        "related_news": related,
        "can_delete": can_delete,
    }


@router.delete("/news/{news_id}")
def delete_news(news_id: int, request: Request):
    user = _require_user(request)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT author_id FROM news WHERE id = :id"), {"id": news_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
        if user["id"] != row.author_id and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")
        for sql in (
            "DELETE FROM news_comments WHERE news_id = :id",
            "DELETE FROM news_likes WHERE news_id = :id",
            "DELETE FROM email_logs WHERE news_id = :id",
            "DELETE FROM news WHERE id = :id",
        ):
            conn.execute(text(sql), {"id": news_id})
        conn.commit()
    return {"success": True}


_SEARCH_SOURCES = sorted({
    "조선일보", "중앙일보", "동아일보", "한겨레", "경향신문", "오마이뉴스", "연합뉴스", "뉴시스",
    "뉴스1", "머니투데이", "매일경제", "한국경제", "서울경제", "전자신문", "ZDNet", "IT World",
    "블로터", "뉴스웍스", "노컷뉴스", "스트레이트뉴스",
})


@router.get("/search")
def search(q: str = "", source: str = ""):
    conditions = ["status = 'published'"]
    params: dict = {}
    if q:
        conditions.append("(title ILIKE :q OR content ILIKE :q)")
        params["q"] = f"%{q}%"
    if source:
        conditions.append("source = :source")
        params["source"] = source
    with engine.connect() as conn:
        items = _rows(conn, f"""
            SELECT id, title, source, created_at, LEFT(content, 300) AS content FROM news
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC LIMIT 100
        """, params)
    return {"news_items": items, "sources": _SEARCH_SOURCES, "q": q, "selected_source": source}


_AGE_GROUP_LABEL = {"teen": "10~20대 추천", "adult": "30~40대 추천", "senior": "50~70대 추천"}


@router.get("/age-news/{group}")
def age_news(group: str, keyword: str = "", page: int = 1):
    config = _AGE_GROUP_CONFIG.get(group)
    if not config:
        raise HTTPException(status_code=404, detail="없는 연령대입니다.")
    page = max(1, page)
    params: dict = {}
    if keyword:
        where = "n.status = 'published' AND COALESCE(n.is_global,0) = 0 AND n.title ILIKE :kw"
        params["kw"] = f"%{keyword}%"
    else:
        cats, kws = config["categories"], config["keywords"]
        cat_ph = ", ".join(f":c{i}" for i in range(len(cats)))
        kw_or = " OR ".join(f"n.title ILIKE :kw{i}" for i in range(len(kws)))
        params.update({f"c{i}": c for i, c in enumerate(cats)})
        params.update({f"kw{i}": f"%{k}%" for i, k in enumerate(kws)})
        where = f"n.status = 'published' AND COALESCE(n.is_global,0) = 0 AND (c.name IN ({cat_ph}) OR ({kw_or}))"
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM news n LEFT JOIN categories c ON n.category_id = c.id WHERE {where}"),
            params,
        ).scalar() or 0
        items = _rows(conn, f"""
            SELECT n.id, n.title, n.image_url, n.created_at, c.name AS category_name
            FROM news n LEFT JOIN categories c ON n.category_id = c.id
            WHERE {where}
            ORDER BY n.created_at DESC
            LIMIT :lim OFFSET :off
        """, {**params, "lim": _AGE_PAGE_SIZE, "off": (page - 1) * _AGE_PAGE_SIZE})
    return {
        "group": group,
        "group_label": _AGE_GROUP_LABEL.get(group, "연령대별 추천"),
        "keywords": config["keywords"],
        "keyword": keyword,
        "news_items": items,
        "page": page,
        "total_pages": max(1, (total + _AGE_PAGE_SIZE - 1) // _AGE_PAGE_SIZE),
        "total": total,
    }


# ── 구독 ──────────────────────────────────────────────────────────────────

class EmailBody(BaseModel):
    email: str


class PaymentConfirmBody(BaseModel):
    paymentKey: str
    orderId: str
    amount: int
    email: str


class TokenBody(BaseModel):
    token: str


@router.get("/subscribe")
def subscribe_state(request: Request):
    user = get_current_user(request)
    state = {
        "categories": [],
        "domestic_subscribed_ids": [],
        "global_subscribed_ids": [],
        "current_email": None,
        "is_subscribed": False,
        "is_verified": False,
        "toss_client_key": settings.TOSS_CLIENT_KEY,
        "skip_payment": settings.SKIP_PAYMENT,
    }
    with engine.connect() as conn:
        state["categories"] = _rows(conn, "SELECT * FROM categories")
        if user:
            p = {"user_id": user["id"]}
            state["domestic_subscribed_ids"] = [r.category_id for r in conn.execute(text(
                "SELECT category_id FROM category_subscriptions WHERE user_id = :user_id AND COALESCE(is_global, 0) = 0"), p)]
            state["global_subscribed_ids"] = [r.category_id for r in conn.execute(text(
                "SELECT category_id FROM category_subscriptions WHERE user_id = :user_id AND is_global = 1"), p)]
            sub = conn.execute(text(
                "SELECT email, is_active, is_verified FROM subscriptions WHERE user_id = :user_id"), p
            ).fetchone()
            if sub:
                state["current_email"] = sub.email
                state["is_subscribed"] = bool(sub.is_active)
                state["is_verified"] = sub.is_verified == 1
    return state


def _start_subscription(user: dict, email: str) -> dict:
    if is_duplicate_subscription(email, user_id=user["id"]):
        raise HTTPException(status_code=409, detail="이미 다른 사용자가 사용 중인 이메일입니다.")
    try:
        token = add_subscription(email, user_id=user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        send_verify_email(email, token, base_url=public_base_url())
    except Exception as e:
        print(f"[EMAIL] 인증 메일 발송 실패: {e}")
    return {"success": True, "mail_sent": True}


@router.post("/subscribe")
def subscribe(body: EmailBody, request: Request):
    """테스트 모드(SKIP_PAYMENT)의 바로 구독, 또는 이미 구독 중인 사용자의 이메일 변경."""
    user = _require_user(request)
    if not settings.SKIP_PAYMENT:
        with engine.connect() as conn:
            active = conn.execute(
                text("SELECT 1 FROM subscriptions WHERE user_id = :uid AND is_active = TRUE"), {"uid": user["id"]}
            ).fetchone()
        if not active:
            raise HTTPException(status_code=402, detail="결제 후 구독할 수 있습니다.")
    return _start_subscription(user, body.email)


@router.post("/subscribe/payment/confirm")
def subscribe_payment_confirm(body: PaymentConfirmBody, request: Request):
    user = _require_user(request)
    auth = base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()
    res = httpx.post(
        "https://api.tosspayments.com/v1/payments/confirm",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        json={"paymentKey": body.paymentKey, "orderId": body.orderId, "amount": body.amount},
        timeout=15,
    )
    if res.status_code != 200:
        raise HTTPException(status_code=400, detail="결제 승인에 실패했습니다.")
    return _start_subscription(user, body.email)


@router.post("/unsubscribe")
def unsubscribe(request: Request):
    user = _require_user(request)
    with engine.connect() as conn:
        conn.execute(text("UPDATE subscriptions SET is_active = FALSE WHERE user_id = :user_id"), {"user_id": user["id"]})
        conn.commit()
    return {"success": True}


@router.post("/verify-email")
def verify_email(body: TokenBody):
    if not body.token or not _do_verify(body.token):
        raise HTTPException(status_code=400, detail="유효하지 않거나 만료된 인증 링크입니다.")
    return {"success": True}


# ── 마이페이지 ────────────────────────────────────────────────────────────

class ProfileBody(BaseModel):
    name: str
    email: str
    tel: str = ""


class PasswordBody(BaseModel):
    current_pw: str
    new_pw: str
    new_pw_confirm: str


@router.get("/mypage")
def mypage(request: Request):
    user = _require_user(request)
    p = {"user_id": user["id"]}
    with engine.connect() as conn:
        sub = conn.execute(text(
            "SELECT email, is_active, is_verified FROM subscriptions WHERE user_id = :user_id"), p
        ).fetchone()
        categories = [r.name for r in conn.execute(text("""
            SELECT c.name FROM category_subscriptions cs
            JOIN categories c ON cs.category_id = c.id
            WHERE cs.user_id = :user_id
        """), p)]
        liked_news = _rows(conn, """
            SELECT n.id, n.title, n.created_at FROM news_likes l
            JOIN news n ON l.news_id = n.id
            WHERE l.user_id = :user_id
            ORDER BY n.created_at DESC
        """, p)
        bookmarked_news = _rows(conn, """
            SELECT n.id, n.title, n.created_at, b.created_at AS saved_at
            FROM bookmarks b JOIN news n ON b.news_id = n.id
            WHERE b.user_id = :user_id
            ORDER BY b.created_at DESC
        """, p)
        my_reports = _rows(conn, """
            SELECT r.id, r.news_id, r.reason, r.status, r.created_at, n.title AS news_title
            FROM reports r LEFT JOIN news n ON r.news_id = n.id
            WHERE r.reporter_id = :user_id
            ORDER BY r.created_at DESC
        """, p)
    return {
        "user": _public_user(user),
        "subscription": dict(sub._mapping) if sub else None,
        "categories": categories,
        "liked_news": liked_news,
        "bookmarked_news": bookmarked_news,
        "my_reports": my_reports,
    }


@router.put("/mypage")
def mypage_update(body: ProfileBody, request: Request):
    user = _require_user(request)
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE news_users SET name=:name, email=:email, tel=:tel WHERE id=:id"),
            {"name": body.name, "email": body.email, "tel": body.tel, "id": user["id"]},
        )
        conn.commit()
    return {"success": True}


@router.post("/mypage/password")
def change_password(body: PasswordBody, request: Request):
    user = _require_user(request)
    if body.new_pw != body.new_pw_confirm:
        raise HTTPException(status_code=400, detail="새 비밀번호가 서로 다릅니다.")
    if len(body.new_pw) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상으로 입력해주세요.")
    if not get_user(user_id=user["id"], password=body.current_pw):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
    with engine.connect() as conn:
        conn.execute(text("UPDATE news_users SET pw=:pw WHERE id=:id"), {"pw": body.new_pw, "id": user["id"]})
        conn.commit()
    return {"success": True}


@router.delete("/mypage")
def withdraw(request: Request):
    uid = _require_user(request)["id"]
    with engine.connect() as conn:
        for sql in (
            "DELETE FROM news_comments WHERE user_id = :id",
            "DELETE FROM news_likes WHERE user_id = :id",
            "DELETE FROM comment_likes WHERE user_id = :id",
            "DELETE FROM bookmarks WHERE user_id = :id",
            "DELETE FROM category_subscriptions WHERE user_id = :id",
            "DELETE FROM subscriptions WHERE user_id = :id",
            "DELETE FROM reports WHERE reporter_id = :id",
            "DELETE FROM news_users WHERE id = :id",
        ):
            conn.execute(text(sql), {"id": uid})
        conn.commit()
    return {"success": True}
