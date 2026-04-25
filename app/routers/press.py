from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from app.database import engine
from app.services.store import is_duplicate_user
from app.routers.pages import AUTH_COOKIE_NAME, get_current_user, render

router = APIRouter(prefix="/press")


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

    return RedirectResponse(url="/?signup_done=1", status_code=303)


@router.get("/write", response_class=HTMLResponse)
async def press_write_page(request: Request) -> HTMLResponse:
    user = get_current_user(request)
    if not user or user["role"] != "press":
        return RedirectResponse(url="/login", status_code=303)
    if not user.get("press_approved"):
        return RedirectResponse(url="/press/news", status_code=303)
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
    if not user.get("press_approved"):
        return RedirectResponse(url="/press/news", status_code=303)

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


@router.get("/edit/{news_id}", response_class=HTMLResponse)
async def press_edit_page(request: Request, news_id: int) -> HTMLResponse:
    user = get_current_user(request)
    if not user or user["role"] != "press":
        return RedirectResponse(url="/login", status_code=303)
    if not user.get("press_approved"):
        return RedirectResponse(url="/press/news", status_code=303)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM news WHERE id = :id AND author_id = :author_id"),
            {"id": news_id, "author_id": user["id"]}
        ).fetchone()
        if not row:
            return RedirectResponse(url="/press/news", status_code=303)
        news = dict(row._mapping)
        categories = [dict(r._mapping) for r in conn.execute(text("SELECT * FROM categories"))]
    return render(request, "press/edit.html", news=news, categories=categories)


@router.post("/edit/{news_id}", response_class=HTMLResponse)
async def press_edit(
    request: Request,
    news_id: int,
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
    if not user.get("press_approved"):
        return RedirectResponse(url="/press/news", status_code=303)
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE news SET title=:title, content=:content, image_url=:image_url,
                source=:source, status=:status, category_id=:category_id
                WHERE id=:id AND author_id=:author_id
            """),
            {
                "title": title, "content": content, "image_url": image_url,
                "source": source, "status": status,
                "category_id": int(category_id) if category_id else None,
                "id": news_id, "author_id": user["id"]
            }
        )
        conn.commit()
    return RedirectResponse(url="/press/news", status_code=303)
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

    return render(request, "press/news.html", news_list=news_list,
                  press_approved=bool(user.get("press_approved")))

@router.get("/delete/{news_id}")
async def press_delete(request: Request, news_id: int):
    user = get_current_user(request)
    if not user or user["role"] != "press":
        return RedirectResponse(url="/login", status_code=303)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM news_comments WHERE news_id = :id"), {"id": news_id})
        conn.execute(text("DELETE FROM news_likes WHERE news_id = :id"), {"id": news_id})
        conn.execute(text("DELETE FROM email_logs WHERE news_id = :id"), {"id": news_id})
        conn.execute(
            text("DELETE FROM news WHERE id = :id AND author_id = :author_id"),
            {"id": news_id, "author_id": user["id"]}
        )
        conn.commit()
    return RedirectResponse(url="/press/news", status_code=303)