import uuid
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File
from sqlalchemy import text
from app.database import engine
from app.services.email import send_newsletter

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/send-newsletter")
def send_newsletter_api(request: Request):
    base_url = str(request.base_url).rstrip("/")
    with engine.connect() as conn:
        # 인증된 구독자만 발송
        subs = conn.execute(
            text("SELECT user_id, email FROM subscriptions WHERE is_active = 1 AND is_verified = 1")
        ).fetchall()

        if not subs:
            return {"success": False, "message": "구독자가 없습니다."}

        total_sent = 0
        last_news_id = None

        for sub in subs:
            user_id = sub.user_id
            email = sub.email

            # 해당 유저가 구독한 카테고리 id 목록
            cat_result = conn.execute(
                text("""
                    SELECT category_id FROM category_subscriptions
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id}
            ).fetchall()

            if not cat_result:
                continue

            category_ids = [row.category_id for row in cat_result]
            placeholders = ",".join(str(i) for i in category_ids)

            # 구독한 카테고리 전체에서 최신 뉴스 5개
            news_rows = conn.execute(
                text(f"""
                    SELECT n.*, c.name as category_name
                    FROM news n
                    LEFT JOIN categories c ON n.category_id = c.id
                    WHERE n.status = 'published' AND n.category_id IN ({placeholders})
                    ORDER BY n.created_at DESC LIMIT 5
                """)
            ).fetchall()

            if not news_rows:
                continue

            for news_row in news_rows:
                news = dict(news_row._mapping)
                send_newsletter(
                    to_emails=[email],
                    title=news["title"],
                    content=news["content"],
                    source=news.get("source", ""),
                    category_name=news.get("category_name", ""),
                    image_url=news.get("image_url", ""),
                    article_link=news.get("link", ""),
                    news_id=news["id"],
                    base_url=base_url,
                )
                total_sent += 1
                last_news_id = news["id"]

        # 발송 로그
        if last_news_id:
            conn.execute(
                text("INSERT INTO email_logs (news_id, recipient_count) VALUES (:news_id, :count)"),
                {"news_id": last_news_id, "count": total_sent}
            )
        conn.commit()

    return {"success": True, "message": f"총 {total_sent}건 발송 완료!"}

from app.services.naver_news import fetch_and_save_news, extract_full_content, clean_article_text

@router.post("/fetch-news")
def fetch_news_api():
    try:
        count = fetch_and_save_news()
        return {"success": True, "message": f"{count}개 뉴스를 가져왔습니다!"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/recrawl-content")
def recrawl_content_api():
    updated = 0
    failed = 0
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, link, content FROM news WHERE link IS NOT NULL AND link != '' ORDER BY id DESC LIMIT 100")
        ).fetchall()
        for row in rows:
            if row.content and len(row.content) >= 300:
                continue
            new_content = extract_full_content(row.link)
            if new_content and len(new_content) > len(row.content or ""):
                conn.execute(
                    text("UPDATE news SET content = :content WHERE id = :id"),
                    {"content": new_content, "id": row.id}
                )
                updated += 1
            else:
                failed += 1
        conn.commit()
    return {"success": True, "message": f"본문 업데이트: {updated}건 성공, {failed}건 실패"}


@router.post("/clean-content")
def clean_content_api():
    cleaned = 0
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, content FROM news WHERE content IS NOT NULL")).fetchall()
        for row in rows:
            original = row.content or ""
            fixed = clean_article_text(original)
            if fixed != original:
                conn.execute(
                    text("UPDATE news SET content = :content WHERE id = :id"),
                    {"content": fixed, "id": row.id}
                )
                cleaned += 1
        conn.commit()
    return {"success": True, "message": f"{cleaned}건의 기사에서 JS 코드를 제거했습니다."}


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return {"success": False, "message": "지원하지 않는 파일 형식입니다."}
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(await file.read())
    return {"success": True, "url": f"/static/uploads/{filename}"}

@router.get("/reports")
def get_reports():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT r.id, r.news_id, r.reporter_id, r.reporter_name,
                   r.reason, r.status, r.created_at,
                   n.title as news_title
            FROM reports r
            LEFT JOIN news n ON r.news_id = n.id
            ORDER BY r.created_at DESC
        """)).fetchall()
    result = []
    for row in rows:
        d = dict(row._mapping)
        if d["created_at"]:
            d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M")
        result.append(d)
    return result


@router.put("/reports/{report_id}")
def update_report(report_id: int, status: str):
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE reports SET status=:status WHERE id=:id"),
            {"status": status, "id": report_id}
        )
        conn.commit()
    return {"success": True}


@router.delete("/reports/{report_id}")
def delete_report(report_id: int):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM reports WHERE id=:id"), {"id": report_id})
        conn.commit()
    return {"success": True}
