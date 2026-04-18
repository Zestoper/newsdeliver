from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

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
    return render(request, "main.html", news_items=get_news_items())


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
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM news WHERE id = :id"),
            {"id": news_id}
        )
        row = result.fetchone()
        news = dict(row._mapping) if row else None
    return render(request, "news_detail.html", news=news)

@router.get("/contact", response_class=HTMLResponse)
async def contact(request: Request) -> HTMLResponse:
    return render(request, "contact.html")
