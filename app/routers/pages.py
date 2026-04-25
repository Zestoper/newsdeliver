from pathlib import Path
import secrets
import httpx
from app.services.naver_news import extract_press_name

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.database import engine
from app.config import settings
from app.services.store import (
    add_subscription,
    add_user,
    get_news_items,
    get_user,
    is_duplicate_subscription,
    is_duplicate_user,
)
from app.services.email import send_verify_email

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

AUTH_COOKIE_NAME = "newsletter_user"


def get_current_user(request: Request) -> dict | None:
    user_id = request.cookies.get(AUTH_COOKIE_NAME)
    if not user_id:
        return None
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM news_users WHERE id = :id"),
            {"id": user_id}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None


def render(
    request: Request,
    template_name: str,
    *,
    message: str | None = None,
    message_type: str = "success",
    form_data: dict | None = None,
    focus: str | None = None,
    **extra_context,
) -> HTMLResponse:
    context = {
        "request": request,
        "current_user": get_current_user(request),
        "message": message,
        "message_type": message_type,
        "form_data": form_data or {},
        "focus": focus,
        **extra_context,
    }
    return templates.TemplateResponse(request, template_name, context)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    with engine.connect() as conn:
        news_items = [dict(r._mapping) for r in conn.execute(text("""
            SELECT n.*, c.name as category_name
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE n.status = 'published'
            ORDER BY n.created_at DESC
        """))]
        top_commented = [dict(r._mapping) for r in conn.execute(text("""
            SELECT n.*, c.name as category_name,
                   COUNT(nc.id) AS comment_count
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            LEFT JOIN news_comments nc ON n.id = nc.news_id
            WHERE n.status = 'published'
            GROUP BY n.id
            ORDER BY comment_count DESC
            LIMIT 5
        """))]
        top_liked = [dict(r._mapping) for r in conn.execute(text("""
            SELECT n.*, c.name as category_name,
                   COUNT(nl.id) AS like_count
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            LEFT JOIN news_likes nl ON n.id = nl.news_id
            WHERE n.status = 'published'
            GROUP BY n.id
            ORDER BY like_count DESC
            LIMIT 5
        """))]
        top_viewed = [dict(r._mapping) for r in conn.execute(text("""
            SELECT n.id, n.title, n.view_count, n.created_at, c.name as category_name
            FROM news n
            LEFT JOIN categories c ON n.category_id = c.id
            WHERE n.status = 'published'
            ORDER BY COALESCE(n.view_count, 0) DESC
            LIMIT 10
        """))]
        # BIG5 언론사별 최신 기사 1건씩 (최대 6건)
        big5_sources = ['조선일보', '중앙일보', '동아일보', '한겨레', '연합뉴스', '경향신문']
        big5_news = []
        for src in big5_sources:
            row = conn.execute(text("""
                SELECT n.*, c.name as category_name
                FROM news n
                LEFT JOIN categories c ON n.category_id = c.id
                WHERE n.status = 'published' AND n.source = :src
                ORDER BY COALESCE(n.view_count, 0) DESC LIMIT 1
            """), {"src": src}).fetchone()
            if row:
                big5_news.append(dict(row._mapping))
    return render(request, "main.html", news_items=news_items,
                  top_commented=top_commented, top_liked=top_liked,
                  big5_news=big5_news, top_viewed=top_viewed)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, message: str | None = None, social_error: str | None = None) -> HTMLResponse:
    social_msg = None
    if social_error:
        labels = {"kakao": "카카오", "naver": "네이버", "google": "구글"}
        label = labels.get(social_error, "소셜")
        social_msg = f"{label} 로그인에 실패했습니다. 앱 키 설정을 확인해주세요."
    return render(request, "login.html",
                  message=social_msg or message,
                  message_type="error" if social_error else "success",
                  has_kakao=bool(settings.KAKAO_CLIENT_ID),
                  has_naver=bool(settings.NAVER_OAUTH_CLIENT_ID),
                  has_google=bool(settings.GOOGLE_CLIENT_ID))


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...),
) -> HTMLResponse:
    form_data = {"user_id": user_id}
    user = get_user(user_id=user_id, password=password)
    if user:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=user_id,
            httponly=True,
            samesite="lax",
        )
        return response
    return render(
        request, "login.html",
        message="아이디 또는 비밀번호가 올바르지 않습니다.",
        message_type="error",
        form_data=form_data,
    )


@router.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(
        url="/login?message=%EB%A1%9C%EA%B7%B8%EC%95%84%EC%9B%83%EB%90%98%EC%97%88%EC%8A%B5%EB%8B%88%EB%8B%A4.",
        status_code=303,
    )
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request) -> HTMLResponse:
    return render(request, "signup.html")


@router.post("/signup", response_class=HTMLResponse)
async def signup(
    request: Request,
    name: str = Form(...),
    birth: str = Form(...),
    user_id: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
) -> HTMLResponse:
    form_data = {
        "name": name,
        "birth": birth,
        "user_id": user_id,
        "email": email,
        "phone": phone,
    }
    if len(password) < 8:
        return render(request, "signup.html",
                      message="비밀번호는 8자 이상으로 입력해주세요.",
                      message_type="error", form_data=form_data)
    dup = is_duplicate_user(user_id=user_id, email=email)
    if dup["id"] and dup["email"]:
        return render(request, "signup.html",
                      message="이미 사용 중인 아이디와 이메일입니다. 둘 다 변경해주세요.",
                      message_type="error", form_data=form_data, focus="user_id")
    if dup["id"]:
        return render(request, "signup.html",
                      message="이미 사용 중인 아이디입니다. 다른 아이디를 입력해주세요.",
                      message_type="error", form_data=form_data, focus="user_id")
    if dup["email"]:
        return render(request, "signup.html",
                      message="이미 사용 중인 이메일입니다. 다른 이메일을 입력해주세요.",
                      message_type="error", form_data=form_data, focus="email")
    add_user({
        "name": name, "birth": birth, "user_id": user_id,
        "password": password, "email": email, "phone": phone,
    })
    return RedirectResponse(url="/", status_code=303)


@router.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(request: Request, verified: str = "", mail_sent: str = "") -> HTMLResponse:
    user = get_current_user(request)
    with engine.connect() as conn:
        categories = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM categories"))]
        subscribed_ids = []
        current_email = None
        is_subscribed = False
        is_verified = False
        verify_link = None
        if user:
            result = conn.execute(
                text("SELECT category_id FROM category_subscriptions WHERE user_id = :user_id"),
                {"user_id": user["id"]}
            )
            subscribed_ids = [row.category_id for row in result]
            sub = conn.execute(
                text("SELECT email, is_active, is_verified, verify_token FROM subscriptions WHERE user_id = :user_id"),
                {"user_id": user["id"]}
            ).fetchone()
            if sub:
                current_email = sub.email
                is_subscribed = sub.is_active == 1
                is_verified = sub.is_verified == 1
                if not is_verified and sub.verify_token:
                    base = str(request.base_url).rstrip('/')
                    verify_link = f"{base}/verify-email?token={sub.verify_token}"
    if verified == "1":
        notify = ("✅ 이메일 인증이 완료되었습니다! 구독이 활성화되었어요.", "success")
    elif mail_sent == "1":
        notify = ("📧 인증 메일을 발송했어요. 이메일을 확인해 인증을 완료해주세요.", "success")
    else:
        notify = (None, "success")
    return render(request, "subscribe.html", categories=categories,
                  subscribed_ids=subscribed_ids, current_email=current_email,
                  is_subscribed=is_subscribed, is_verified=is_verified,
                  verify_link=verify_link,
                  toss_client_key=settings.TOSS_CLIENT_KEY,
                  skip_payment=settings.SKIP_PAYMENT,
                  message=notify[0], message_type=notify[1])


@router.post("/subscribe", response_class=HTMLResponse)
async def subscribe(request: Request, email: str = Form(...)) -> HTMLResponse:
    form_data = {"email": email}
    user = get_current_user(request)

    def get_subscribe_context():
        with engine.connect() as conn:
            categories = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM categories"))]
            subscribed_ids = [row.category_id for row in conn.execute(
                text("SELECT category_id FROM category_subscriptions WHERE user_id = :user_id"),
                {"user_id": user["id"]}
            )]
            sub = conn.execute(
                text("SELECT email, is_active, is_verified FROM subscriptions WHERE user_id = :user_id"),
                {"user_id": user["id"]}
            ).fetchone()
            current_email = sub.email if sub else None
            is_subscribed = sub.is_active == 1 if sub else False
            is_verified = sub.is_verified == 1 if sub else False
        return categories, subscribed_ids, current_email, is_subscribed, is_verified

    if not user:
        with engine.connect() as conn:
            categories = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM categories"))]
        return render(request, "subscribe.html",
                      message="로그인 후 구독할 수 있습니다.",
                      message_type="error", form_data=form_data,
                      categories=categories, subscribed_ids=[],
                      current_email=None, is_subscribed=False, is_verified=False,
                      verify_link=None)

    if is_duplicate_subscription(email, user_id=user["id"]):
        categories, subscribed_ids, current_email, is_subscribed, is_verified = get_subscribe_context()
        return render(request, "subscribe.html",
                      message="이미 다른 사용자가 사용 중인 이메일입니다.",
                      message_type="error", form_data=form_data,
                      categories=categories, subscribed_ids=subscribed_ids,
                      current_email=current_email, is_subscribed=is_subscribed,
                      is_verified=is_verified, verify_link=None)

    try:
        token = add_subscription(email, user_id=user["id"])
    except ValueError as e:
        categories, subscribed_ids, current_email, is_subscribed, is_verified = get_subscribe_context()
        return render(request, "subscribe.html",
                      message=str(e), message_type="error",
                      categories=categories, subscribed_ids=subscribed_ids,
                      current_email=current_email, is_subscribed=is_subscribed,
                      is_verified=is_verified, verify_link=None)

    try:
        send_verify_email(email, token, base_url=str(request.base_url))
    except Exception:
        pass

    return RedirectResponse(url="/subscribe?mail_sent=1", status_code=303)


@router.get("/subscribe/payment/success", response_class=HTMLResponse)
async def subscribe_payment_success(
    request: Request,
    paymentKey: str = "",  # 서버사이드 승인 시 사용
    orderId: str = "",     # 서버사이드 승인 시 사용
    amount: int = 0,       # 서버사이드 승인 시 사용
    email: str = "",
) -> HTMLResponse:
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not email:
        return RedirectResponse(url="/subscribe?pay_error=1", status_code=303)

    # Toss 서버사이드 결제 승인
    import httpx as _httpx, base64 as _base64
    _auth = _base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()
    _res = _httpx.post(
        "https://api.tosspayments.com/v1/payments/confirm",
        headers={"Authorization": f"Basic {_auth}", "Content-Type": "application/json"},
        json={"paymentKey": paymentKey, "orderId": orderId, "amount": amount},
    )
    if _res.status_code != 200:
        return RedirectResponse(url="/subscribe?pay_error=1", status_code=303)

    if is_duplicate_subscription(email, user_id=user["id"]):
        return RedirectResponse(url="/subscribe?mail_sent=1", status_code=303)

    try:
        token = add_subscription(email, user_id=user["id"])
    except ValueError:
        return RedirectResponse(url="/subscribe?mail_sent=1", status_code=303)

    try:
        send_verify_email(email, token, base_url=str(request.base_url))
    except Exception:
        pass

    return RedirectResponse(url="/subscribe?mail_sent=1", status_code=303)


@router.get("/subscribe/payment/fail", response_class=HTMLResponse)
async def subscribe_payment_fail() -> HTMLResponse:
    return RedirectResponse(url="/subscribe?pay_error=1", status_code=303)


def _do_verify(token: str) -> bool:
    """토큰으로 구독 인증 처리. 성공 여부 반환."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM subscriptions WHERE verify_token = :token"),
            {"token": token}
        ).fetchone()
        if not row:
            return False
        conn.execute(
            text("UPDATE subscriptions SET is_verified = 1, is_active = 1 WHERE verify_token = :token"),
            {"token": token}
        )
        conn.commit()
    return True


@router.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request, token: str = ""):
    if not token:
        return render(request, "verify_email.html", valid=False, email="", token="")
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT email FROM subscriptions WHERE verify_token = :token"),
            {"token": token}
        ).fetchone()
    if not row:
        return render(request, "verify_email.html", valid=False, email="", token="")
    # 링크 클릭 즉시 인증 완료
    _do_verify(token)
    return RedirectResponse(url="/subscribe?verified=1", status_code=303)


@router.post("/verify-email/confirm", response_class=HTMLResponse)
async def verify_email_confirm(request: Request, token: str = Form(...)):
    success = _do_verify(token)
    if not success:
        return render(request, "verify_email.html", valid=False, email="", token="")
    return RedirectResponse(url="/subscribe?verified=1", status_code=303)


@router.post("/unsubscribe")
async def unsubscribe(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE subscriptions SET is_active = 0 WHERE user_id = :user_id"),
            {"user_id": user["id"]}
        )
        conn.commit()
    return RedirectResponse(url="/subscribe", status_code=303)


@router.get("/mypage", response_class=HTMLResponse)
async def mypage(request: Request) -> HTMLResponse:
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    with engine.connect() as conn:
        sub = conn.execute(
            text("SELECT email, is_active, is_verified FROM subscriptions WHERE user_id = :user_id"),
            {"user_id": user["id"]}
        ).fetchone()
        cat_result = conn.execute(
            text("""
                SELECT c.name FROM category_subscriptions cs
                JOIN categories c ON cs.category_id = c.id
                WHERE cs.user_id = :user_id
            """),
            {"user_id": user["id"]}
        ).fetchall()
        liked_news_result = conn.execute(
            text("""
                SELECT n.id, n.title, n.created_at FROM news_likes l
                JOIN news n ON l.news_id = n.id
                WHERE l.user_id = :user_id
                ORDER BY n.created_at DESC
            """),
            {"user_id": user["id"]}
        ).fetchall()
        bookmarked_news_result = conn.execute(
            text("""
                SELECT n.id, n.title, n.created_at, b.created_at as saved_at
                FROM bookmarks b
                JOIN news n ON b.news_id = n.id
                WHERE b.user_id = :user_id
                ORDER BY b.created_at DESC
            """),
            {"user_id": user["id"]}
        ).fetchall()
    subscription = dict(sub._mapping) if sub else None
    categories = [row.name for row in cat_result]
    liked_news = [dict(row._mapping) for row in liked_news_result]
    bookmarked_news = [dict(row._mapping) for row in bookmarked_news_result]
    return render(request, "mypage.html", subscription=subscription,
                  categories=categories, liked_news=liked_news,
                  bookmarked_news=bookmarked_news)


@router.post("/mypage", response_class=HTMLResponse)
async def mypage_update(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    tel: str = Form(""),
) -> HTMLResponse:
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE news_users SET name=:name, email=:email, tel=:tel WHERE id=:id"),
            {"name": name, "email": email, "tel": tel, "id": user["id"]}
        )
        conn.commit()
    return RedirectResponse(url="/mypage", status_code=303)


@router.post("/mypage/change-password")
async def change_password(
    request: Request,
    current_pw: str = Form(...),
    new_pw: str = Form(...),
    new_pw_confirm: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if new_pw != new_pw_confirm:
        return RedirectResponse(url="/mypage?pw_error=confirm", status_code=303)
    if len(new_pw) < 8:
        return RedirectResponse(url="/mypage?pw_error=short", status_code=303)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM news_users WHERE id=:id AND pw=:pw"),
            {"id": user["id"], "pw": current_pw}
        ).fetchone()
        if not row:
            return RedirectResponse(url="/mypage?pw_error=wrong", status_code=303)
        conn.execute(
            text("UPDATE news_users SET pw=:pw WHERE id=:id"),
            {"pw": new_pw, "id": user["id"]}
        )
        conn.commit()
    return RedirectResponse(url="/mypage?pw_success=1", status_code=303)


_NEWS_PAGE_SIZE = 20

@router.get("/news", response_class=HTMLResponse)
async def news(request: Request, category: str = "", page: int = 1) -> HTMLResponse:
    page = max(1, page)
    offset = (page - 1) * _NEWS_PAGE_SIZE
    with engine.connect() as conn:
        categories = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM categories"))]
        if category:
            total_count = conn.execute(
                text("""SELECT COUNT(*) FROM news n
                        LEFT JOIN categories c ON n.category_id = c.id
                        WHERE n.status = 'published' AND c.name = :category"""),
                {"category": category}
            ).scalar() or 0
            result = conn.execute(
                text("""
                    SELECT n.*, c.name as category_name
                    FROM news n
                    LEFT JOIN categories c ON n.category_id = c.id
                    WHERE n.status = 'published' AND c.name = :category
                    ORDER BY n.created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"category": category, "limit": _NEWS_PAGE_SIZE, "offset": offset}
            )
        else:
            total_count = conn.execute(
                text("SELECT COUNT(*) FROM news WHERE status = 'published'")
            ).scalar() or 0
            result = conn.execute(
                text("""
                    SELECT n.*, c.name as category_name
                    FROM news n
                    LEFT JOIN categories c ON n.category_id = c.id
                    WHERE n.status = 'published'
                    ORDER BY n.created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": _NEWS_PAGE_SIZE, "offset": offset}
            )
        news_items = [dict(row._mapping) for row in result]
    total_pages = max(1, (total_count + _NEWS_PAGE_SIZE - 1) // _NEWS_PAGE_SIZE)
    return render(request, "news.html", news_items=news_items,
                  categories=categories, selected_category=category,
                  page=page, total_pages=total_pages)


@router.get("/news/{news_id}", response_class=HTMLResponse)
async def news_detail(request: Request, news_id: int) -> HTMLResponse:
    user = get_current_user(request)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM news WHERE id = :id"), {"id": news_id}
        ).fetchone()
        news = dict(row._mapping) if row else None
        # 조회수 증가
        if news:
            conn.execute(
                text("UPDATE news SET view_count = COALESCE(view_count, 0) + 1 WHERE id = :id"),
                {"id": news_id}
            )
            conn.commit()
            news["view_count"] = (news.get("view_count") or 0) + 1
        like_count = conn.execute(
            text("SELECT COUNT(*) FROM news_likes WHERE news_id = :id"), {"id": news_id}
        ).scalar()
        liked = False
        bookmarked = False
        subscribed = False
        if user:
            liked = conn.execute(
                text("SELECT id FROM news_likes WHERE news_id = :news_id AND user_id = :user_id"),
                {"news_id": news_id, "user_id": user["id"]}
            ).fetchone() is not None
            bookmarked = conn.execute(
                text("SELECT id FROM bookmarks WHERE news_id = :news_id AND user_id = :user_id"),
                {"news_id": news_id, "user_id": user["id"]}
            ).fetchone() is not None
            sub = conn.execute(
                text("SELECT is_active FROM subscriptions WHERE user_id = :user_id"),
                {"user_id": user["id"]}
            ).fetchone()
            subscribed = bool(sub and sub.is_active)
        # 관련 뉴스 (같은 카테고리, 조회수 높은 순)
        related_news = []
        if news and news.get("category_id"):
            related_rows = conn.execute(
                text("""
                    SELECT n.*, c.name as category_name
                    FROM news n
                    LEFT JOIN categories c ON n.category_id = c.id
                    WHERE n.status = 'published'
                      AND n.category_id = :cat_id
                      AND n.id != :news_id
                    ORDER BY COALESCE(n.view_count, 0) DESC
                    LIMIT 4
                """),
                {"cat_id": news["category_id"], "news_id": news_id}
            ).fetchall()
            related_news = [dict(r._mapping) for r in related_rows]
    return render(request, "news_detail.html", news=news,
                  like_count=like_count, liked=liked, bookmarked=bookmarked,
                  subscribed=subscribed, related_news=related_news)


@router.get("/news/{news_id}/delete")
async def delete_news_page(request: Request, news_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM news WHERE id = :id"), {"id": news_id}
        ).fetchone()
        if not row:
            return RedirectResponse(url="/", status_code=303)
        news = dict(row._mapping)
        if user["id"] != news["author_id"] and user["role"] != "admin":
            return RedirectResponse(url=f"/news/{news_id}", status_code=303)
        conn.execute(text("DELETE FROM news_comments WHERE news_id = :id"), {"id": news_id})
        conn.execute(text("DELETE FROM news_likes WHERE news_id = :id"), {"id": news_id})
        conn.execute(text("DELETE FROM email_logs WHERE news_id = :id"), {"id": news_id})
        conn.execute(text("DELETE FROM news WHERE id = :id"), {"id": news_id})
        conn.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = "", source: str = "") -> HTMLResponse:
    # 실제 수집하는 언론사만 필터에 노출
    from app.services.naver_news import extract_press_name
    domain_map = {
        "chosun": "조선일보", "joongang": "중앙일보", "donga": "동아일보",
        "hani": "한겨레", "khan": "경향신문", "ohmynews": "오마이뉴스",
        "yonhap": "연합뉴스", "yna": "연합뉴스", "newsis": "뉴시스",
        "news1": "뉴스1", "mt": "머니투데이", "mk": "매일경제",
        "hankyung": "한국경제", "sedaily": "서울경제", "etnews": "전자신문",
        "zdnet": "ZDNet", "itworld": "IT World", "bloter": "블로터",
        "newsworks": "뉴스웍스", "nocutnews": "노컷뉴스", "straightnews": "스트레이트뉴스",
    }
    sources = sorted(set(domain_map.values()))
    with engine.connect() as conn:
        conditions = ["status = 'published'"]
        params = {}
        if q:
            conditions.append("(title LIKE :q OR content LIKE :q)")
            params["q"] = f"%{q}%"
        if source:
            conditions.append("source = :source")
            params["source"] = source
        where = " AND ".join(conditions)
        news_items = [dict(row._mapping) for row in conn.execute(
            text(f"SELECT * FROM news WHERE {where} ORDER BY created_at DESC"),
            params
        )]
    return render(request, "search.html", news_items=news_items,
                  sources=sources, q=q, selected_source=source)


@router.get("/contact", response_class=HTMLResponse)
async def contact(request: Request) -> HTMLResponse:
    return render(request, "contact.html")


@router.post("/news/{news_id}/bookmark")
async def toggle_bookmark(request: Request, news_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM bookmarks WHERE news_id = :news_id AND user_id = :user_id"),
            {"news_id": news_id, "user_id": user["id"]}
        ).fetchone()
        if existing:
            conn.execute(
                text("DELETE FROM bookmarks WHERE news_id = :news_id AND user_id = :user_id"),
                {"news_id": news_id, "user_id": user["id"]}
            )
            saved = False
        else:
            conn.execute(
                text("INSERT INTO bookmarks (news_id, user_id) VALUES (:news_id, :user_id)"),
                {"news_id": news_id, "user_id": user["id"]}
            )
            saved = True
        conn.commit()
    return JSONResponse({"success": True, "saved": saved})


@router.post("/news/{news_id}/like")
async def toggle_like(request: Request, news_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM news_likes WHERE news_id = :news_id AND user_id = :user_id"),
            {"news_id": news_id, "user_id": user["id"]}
        ).fetchone()
        if existing:
            conn.execute(
                text("DELETE FROM news_likes WHERE news_id = :news_id AND user_id = :user_id"),
                {"news_id": news_id, "user_id": user["id"]}
            )
            liked = False
        else:
            conn.execute(
                text("INSERT INTO news_likes (news_id, user_id) VALUES (:news_id, :user_id)"),
                {"news_id": news_id, "user_id": user["id"]}
            )
            liked = True
        conn.commit()
        count = conn.execute(
            text("SELECT COUNT(*) FROM news_likes WHERE news_id = :news_id"),
            {"news_id": news_id}
        ).scalar()
    return JSONResponse({"success": True, "liked": liked, "count": count})


@router.get("/news/{news_id}/comments")
async def get_comments(request: Request, news_id: int):
    user = get_current_user(request)
    uid = user["id"] if user else None
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT c.id, c.content, c.created_at, c.user_id, c.parent_id, u.name,
                       COUNT(cl.id) AS like_count
                FROM news_comments c
                JOIN news_users u ON c.user_id = u.id
                LEFT JOIN comment_likes cl ON cl.comment_id = c.id
                WHERE c.news_id = :news_id
                GROUP BY c.id
                ORDER BY COALESCE(c.parent_id, c.id), c.id ASC
            """),
            {"news_id": news_id}
        )
        comments = [dict(row._mapping) for row in result]
        # 현재 유저가 좋아요한 댓글 id 목록
        liked_ids = set()
        if uid:
            rows = conn.execute(
                text("SELECT comment_id FROM comment_likes WHERE user_id = :uid"),
                {"uid": uid}
            ).fetchall()
            liked_ids = {r.comment_id for r in rows}
    for c in comments:
        if c["created_at"]:
            c["created_at"] = c["created_at"].strftime("%Y-%m-%d %H:%M")
        c["liked"] = c["id"] in liked_ids
    return JSONResponse(comments)


@router.post("/news/{news_id}/comments/{comment_id}/like")
async def toggle_comment_like(request: Request, news_id: int, comment_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM comment_likes WHERE comment_id=:cid AND user_id=:uid"),
            {"cid": comment_id, "uid": user["id"]}
        ).fetchone()
        if existing:
            conn.execute(
                text("DELETE FROM comment_likes WHERE comment_id=:cid AND user_id=:uid"),
                {"cid": comment_id, "uid": user["id"]}
            )
            liked = False
        else:
            conn.execute(
                text("INSERT INTO comment_likes (comment_id, user_id) VALUES (:cid, :uid)"),
                {"cid": comment_id, "uid": user["id"]}
            )
            liked = True
        conn.commit()
        count = conn.execute(
            text("SELECT COUNT(*) FROM comment_likes WHERE comment_id=:cid"),
            {"cid": comment_id}
        ).scalar()
    return JSONResponse({"success": True, "liked": liked, "count": count})


@router.post("/news/{news_id}/comments")
async def add_comment(
    request: Request,
    news_id: int,
    content: str = Form(...),
    parent_id: int | None = Form(None),
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO news_comments (news_id, user_id, content, parent_id) VALUES (:news_id, :user_id, :content, :parent_id)"),
            {"news_id": news_id, "user_id": user["id"], "content": content, "parent_id": parent_id}
        )
        conn.commit()
    return JSONResponse({"success": True})


@router.put("/news/{news_id}/comments/{comment_id}")
async def update_comment(request: Request, news_id: int, comment_id: int, content: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE news_comments SET content = :content WHERE id = :id AND user_id = :user_id"),
            {"content": content, "id": comment_id, "user_id": user["id"]}
        )
        conn.commit()
    return JSONResponse({"success": True})


@router.delete("/news/{news_id}/comments/{comment_id}")
async def delete_comment(request: Request, news_id: int, comment_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM news_comments WHERE id = :id AND user_id = :user_id"),
            {"id": comment_id, "user_id": user["id"]}
        )
        conn.commit()
    return JSONResponse({"success": True})


@router.post("/news/{news_id}/report")
async def report_news(request: Request, news_id: int, reason: str = Form("")):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        # 하루 신고 횟수 체크 (최대 10건)
        today_count = conn.execute(
            text("SELECT COUNT(*) FROM reports WHERE reporter_id=:uid AND DATE(created_at)=CURDATE()"),
            {"uid": user["id"]}
        ).scalar()
        if today_count >= 10:
            return JSONResponse({"success": False, "message": "오늘 신고 가능 횟수(10건)를 초과했습니다. 추가 신고는 관리자에게 문의해주세요."})
        existing = conn.execute(
            text("SELECT id FROM reports WHERE news_id=:nid AND reporter_id=:uid"),
            {"nid": news_id, "uid": user["id"]}
        ).fetchone()
        if existing:
            return JSONResponse({"success": False, "message": "이미 신고한 게시글입니다."})
        conn.execute(
            text("INSERT INTO reports (news_id, reporter_id, reporter_name, reason) VALUES (:nid, :uid, :name, :reason)"),
            {"nid": news_id, "uid": user["id"], "name": user["name"], "reason": reason}
        )
        conn.commit()
    return JSONResponse({"success": True, "message": "신고가 접수되었습니다."})


@router.get("/categories")
async def get_categories():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM categories"))
        return JSONResponse([dict(row._mapping) for row in result])


@router.post("/categories/{category_id}/subscribe")
async def toggle_category_subscribe(request: Request, category_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM category_subscriptions WHERE user_id = :user_id AND category_id = :category_id"),
            {"user_id": user["id"], "category_id": category_id}
        ).fetchone()
        if existing:
            conn.execute(
                text("DELETE FROM category_subscriptions WHERE user_id = :user_id AND category_id = :category_id"),
                {"user_id": user["id"], "category_id": category_id}
            )
            subscribed = False
        else:
            conn.execute(
                text("INSERT INTO category_subscriptions (user_id, category_id) VALUES (:user_id, :category_id)"),
                {"user_id": user["id"], "category_id": category_id}
            )
            subscribed = True
        conn.commit()
    return JSONResponse({"success": True, "subscribed": subscribed})


@router.get("/api/market")
async def market_data():
    """KOSPI·KOSDAQ·환율 데이터 프록시"""
    result = {}
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    async with httpx.AsyncClient(timeout=5, headers=headers) as client:
        # 지수
        for code in ("KOSPI", "KOSDAQ"):
            try:
                r = await client.get(f"https://m.stock.naver.com/api/index/{code}/basic")
                d = r.json()
                result[code] = {
                    "value": d.get("closePrice", "-"),
                    "change": d.get("compareToPreviousClosePrice", "0"),
                    "rate": d.get("fluctuationsRatio", "0"),
                    "state": d.get("fluctuationCode", "EVEN"),
                }
            except Exception:
                pass

        # 환율 (USD 기준)
        try:
            r = await client.get("https://open.er-api.com/v6/latest/USD")
            rates = r.json().get("rates", {})
            krw = rates.get("KRW", 0)
            result["USD_KRW"] = round(krw)
            if rates.get("EUR"):
                result["EUR_KRW"] = round(krw / rates["EUR"])
            if rates.get("JPY"):
                result["JPY_KRW"] = round(krw / rates["JPY"] * 100)
            if rates.get("CNY"):
                result["CNY_KRW"] = round(krw / rates["CNY"])
        except Exception:
            pass

    return result


@router.get("/my-subscriptions")
async def my_subscriptions(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse([])
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT c.id, c.name
                FROM category_subscriptions cs
                JOIN categories c ON cs.category_id = c.id
                WHERE cs.user_id = :user_id
            """),
            {"user_id": user["id"]}
        )
        return JSONResponse([dict(row._mapping) for row in result])