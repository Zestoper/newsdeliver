from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.database import engine
from app.services.store import is_duplicate_user

router = APIRouter(prefix="/press")

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


def render(request, template_name, *, message=None, message_type="success", form_data=None, focus=None, **extra):
    context = {
        "request": request,
        "current_user": get_current_user(request),
        "message": message,
        "message_type": message_type,
        "form_data": form_data or {},
        "focus": focus,
        **extra,
    }
    return templates.TemplateResponse(request, template_name, context)


# ── 회원가입 ──
@router.get("/signup", response_class=HTMLResponse)
async def press_signup_page(request: Request) -> HTMLResponse:
    return render(request, "press/signup.html")


@router.post("/signup", response_class=HTMLResponse)
async def press_signup(
    request: Request,
    name: str = Form(...),
    birth: str = Form(...),
    user_id: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
) -> HTMLResponse:
    form_data = {"name": name, "birth": birth, "user_id": user_id, "email": email, "phone": phone}

    if len(password) < 8:
        return render(request, "press/signup.html",
                      message="비밀번호는 8자 이상으로 입력해주세요.",
                      message_type="error", form_data=form_data)

    dup = is_duplicate_user(user_id=user_id, email=email)
    if dup["id"] and dup["email"]:
        return render(request, "press/signup.html",
                      message="이미 사용 중인 아이디와 이메일입니다.",
                      message_type="error", form_data=form_data, focus="user_id")
    if dup["id"]:
        return render(request, "press/signup.html",
                      message="이미 사용 중인 아이디입니다.",
                      message_type="error", form_data=form_data, focus="user_id")
    if dup["email"]:
        return render(request, "press/signup.html",
                      message="이미 사용 중인 이메일입니다.",
                      message_type="error", form_data=form_data, focus="email")

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO news_users (id, name, birth, pw, email, tel, role)
                VALUES (:id, :name, :birth, :pw, :email, :tel, 'press')
            """),
            {"id": user_id, "name": name, "birth": birth,
             "pw": password, "email": email, "tel": phone}
        )
        conn.commit()

    return render(request, "press/signup.html",
                  message="가입이 완료되었습니다! 로그인해주세요.",
                  message_type="success")


@router.get("/write", response_class=HTMLResponse)
async def press_write_page(request: Request) -> HTMLResponse:
    user = get_current_user(request)
    if not user or user["role"] != "press":
        return RedirectResponse(url="/login", status_code=303)
    with engine.connect() as conn:
        categories = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM categories"))]
    return render(request, "press/write.html", categories=categories)


@router.post("/write", response_class=HTMLResponse)
async def press_write(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    source: str = Form(""),
    image_url: str = Form(""),
    status: str = Form("draft"),
    category_id: str = Form(""),
) -> HTMLResponse:
    user = get_current_user(request)
    if not user or user["role"] != "press":
        return RedirectResponse(url="/login", status_code=303)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO news (title, content, image_url, source, status, author_id, category_id)
                VALUES (:title, :content, :image_url, :source, :status, :author_id, :category_id)
            """),
            {
                "title": title, "content": content, "image_url": image_url,
                "source": source, "status": status, "author_id": user["id"],
                "category_id": int(category_id) if category_id else None
            }
        )
        conn.commit()
    return RedirectResponse(url="/press/news", status_code=303)

@router.post("/write", response_class=HTMLResponse)
async def press_write(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    source: str = Form(""),
    image_url: str = Form(""),
    status: str = Form("draft"),
) -> HTMLResponse:
    user = get_current_user(request)
    if not user or user["role"] != "press":
        return RedirectResponse(url="/login", status_code=303)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO news (title, content, image_url, source, status, author_id)
                VALUES (:title, :content, :image_url, :source, :status, :author_id)
            """),
            {"title": title, "content": content, "image_url": image_url,
             "source": source, "status": status, "author_id": user["id"]}
        )
        conn.commit()

    return RedirectResponse(url="/press/news", status_code=303)


# ── 내 뉴스 관리 ──
@router.get("/news", response_class=HTMLResponse)
async def press_news_page(request: Request) -> HTMLResponse:
    user = get_current_user(request)
    if not user or user["role"] != "press":
        return RedirectResponse(url="/login", status_code=303)

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM news WHERE author_id = :author_id ORDER BY created_at DESC"),
            {"author_id": user["id"]}
        )
        news_list = [dict(row._mapping) for row in result]

    return render(request, "press/news.html", news_list=news_list)