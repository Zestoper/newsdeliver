from pathlib import Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from app.database import engine
from app.services.store import (
    add_subscription,
    add_user,
    get_news_items,
    get_user,
    is_duplicate_subscription,
    is_duplicate_user,
)

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
    user = get_current_user(request)
    with engine.connect() as conn:
        if user:
            # 구독한 카테고리 있으면 해당 뉴스만
            result = conn.execute(
                text("SELECT category_id FROM category_subscriptions WHERE user_id = :user_id"),
                {"user_id": user["id"]}
            )
            subscribed_ids = [row.category_id for row in result]

            if subscribed_ids:
                placeholders = ",".join(str(i) for i in subscribed_ids)
                news_items = [dict(row._mapping) for row in conn.execute(
                    text(f"SELECT * FROM news WHERE status = 'published' AND category_id IN ({placeholders}) ORDER BY created_at ASC")
                )]
            else:
                news_items = get_news_items()
        else:
            news_items = get_news_items()

    return render(request, "main.html", news_items=news_items)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, message: str | None = None) -> HTMLResponse:
    return render(request, "login.html", message=message, message_type="success")


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
        request,
        "login.html",
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
        return render(
            request,
            "signup.html",
            message="비밀번호는 8자 이상으로 입력해주세요.",
            message_type="error",
            form_data=form_data,
        )

    dup = is_duplicate_user(user_id=user_id, email=email)

    if dup["id"] and dup["email"]:
        return render(
            request, "signup.html",
            message="이미 사용 중인 아이디와 이메일입니다. 둘 다 변경해주세요.",
            message_type="error",
            form_data=form_data,
            focus="user_id",
        )
    if dup["id"]:
        return render(
            request, "signup.html",
            message="이미 사용 중인 아이디입니다. 다른 아이디를 입력해주세요.",
            message_type="error",
            form_data=form_data,
            focus="user_id",
        )
    if dup["email"]:
        return render(
            request, "signup.html",
            message="이미 사용 중인 이메일입니다. 다른 이메일을 입력해주세요.",
            message_type="error",
            form_data=form_data,
            focus="email",
        )

    add_user({
        "name": name,
        "birth": birth,
        "user_id": user_id,
        "password": password,
        "email": email,
        "phone": phone,
    })
    return render(
        request, "signup.html",
        message="회원가입이 완료되었습니다!",
        message_type="success",
    )


@router.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(request: Request) -> HTMLResponse:
    return render(request, "subscribe.html")


@router.post("/subscribe", response_class=HTMLResponse)
async def subscribe(request: Request, email: str = Form(...)) -> HTMLResponse:
    form_data = {"email": email}
    user = get_current_user(request)

    if not user:
        return render(
            request,
            "subscribe.html",
            message="로그인 후 구독할 수 있습니다.",
            message_type="error",
            form_data=form_data,
        )

    if is_duplicate_subscription(email):
        return render(
            request,
            "subscribe.html",
            message="이미 구독 중인 이메일입니다.",
            message_type="error",
            form_data=form_data,
        )

    add_subscription(email, user_id=user["id"])
    return render(
        request,
        "subscribe.html",
        message="구독이 완료되었습니다. 다음 뉴스레터부터 받아볼 수 있어요.",
        message_type="success",
    )


@router.get("/news", response_class=HTMLResponse)
async def news(request: Request) -> HTMLResponse:
    return render(request, "news.html", news_items=get_news_items())

@router.get("/news/{news_id}", response_class=HTMLResponse)
async def news_detail(request: Request, news_id: int) -> HTMLResponse:
    user = get_current_user(request)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM news WHERE id = :id"),
            {"id": news_id}
        ).fetchone()
        news = dict(row._mapping) if row else None

        like_count = conn.execute(
            text("SELECT COUNT(*) FROM news_likes WHERE news_id = :id"),
            {"id": news_id}
        ).scalar()

        liked = False
        if user:
            liked = conn.execute(
                text("SELECT id FROM news_likes WHERE news_id = :news_id AND user_id = :user_id"),
                {"news_id": news_id, "user_id": user["id"]}
            ).fetchone() is not None

        # 구독 여부
        subscribed = False
        if user:
            subscribed = conn.execute(
                text("SELECT id FROM subscriptions WHERE user_id = :user_id AND is_active = 1"),
                {"user_id": user["id"]}
            ).fetchone() is not None

    return render(request, "news_detail.html", news=news,
                  like_count=like_count, liked=liked, subscribed=subscribed)
@router.get("/contact", response_class=HTMLResponse)
async def contact(request: Request) -> HTMLResponse:
    return render(request, "contact.html")

# 좋아요 토글
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


# 댓글 목록 조회
@router.get("/news/{news_id}/comments")
async def get_comments(request: Request, news_id: int):
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT c.id, c.content, c.created_at, u.name
                FROM news_comments c
                JOIN news_users u ON c.user_id = u.id
                WHERE c.news_id = :news_id
                ORDER BY c.created_at ASC
            """),
            {"news_id": news_id}
        )
        comments = [dict(row._mapping) for row in result]
    for c in comments:
        if c["created_at"]:
            c["created_at"] = c["created_at"].strftime("%Y-%m-%d %H:%M")
    return JSONResponse(comments)


# 댓글 작성
@router.post("/news/{news_id}/comments")
async def add_comment(request: Request, news_id: int, content: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "message": "로그인이 필요합니다."})
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO news_comments (news_id, user_id, content) VALUES (:news_id, :user_id, :content)"),
            {"news_id": news_id, "user_id": user["id"], "content": content}
        )
        conn.commit()
    return JSONResponse({"success": True})


# 댓글 삭제
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

# 카테고리 목록 조회
@router.get("/categories")
async def get_categories():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM categories"))
        return JSONResponse([dict(row._mapping) for row in result])


# 카테고리 구독 토글
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


# 내 구독 카테고리 조회
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
    

@router.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(request: Request) -> HTMLResponse:
    user = get_current_user(request)
    with engine.connect() as conn:
        # 전체 카테고리
        categories = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM categories"))]
        # 내가 구독한 카테고리 id 목록
        subscribed_ids = []
        if user:
            result = conn.execute(
                text("SELECT category_id FROM category_subscriptions WHERE user_id = :user_id"),
                {"user_id": user["id"]}
            )
            subscribed_ids = [row.category_id for row in result]
    return render(request, "subscribe.html", categories=categories, subscribed_ids=subscribed_ids)