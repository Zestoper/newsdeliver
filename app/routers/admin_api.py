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

        for sub in subs:
            user_id = sub.user_id
            email = sub.email

            cat_result = conn.execute(
                text("SELECT category_id FROM category_subscriptions WHERE user_id = :user_id"),
                {"user_id": user_id}
            ).fetchall()

            if not cat_result:
                continue

            category_ids = [row.category_id for row in cat_result]
            placeholders = ",".join(str(i) for i in category_ids)

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

            articles = [dict(row._mapping) for row in news_rows]
            ok = send_newsletter(to_email=email, articles=articles, base_url=base_url)
            if ok:
                total_sent += 1

        conn.commit()

    return {"success": True, "message": f"총 {total_sent}명에게 발송 완료!"}

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
            text("SELECT id, link, content FROM news WHERE link IS NOT NULL AND link != '' ORDER BY id DESC")
        ).fetchall()
        for row in rows:
            if row.content and len(row.content) >= 1000:
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

@router.get("/subscribers")
def get_subscribers():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT s.id, s.user_id, u.name, s.email,
                   s.is_active, s.is_verified, s.created_at,
                   GROUP_CONCAT(c.name ORDER BY c.name SEPARATOR ', ') AS categories
            FROM subscriptions s
            LEFT JOIN news_users u ON s.user_id = u.id
            LEFT JOIN category_subscriptions cs ON cs.user_id = s.user_id
            LEFT JOIN categories c ON cs.category_id = c.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """)).fetchall()
    result = []
    for row in rows:
        d = dict(row._mapping)
        if d["created_at"]:
            d["created_at"] = d["created_at"].strftime("%Y-%m-%d")
        result.append(d)
    return result


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


@router.get("/stats")
def get_stats():
    with engine.connect() as conn:
        total_users = conn.execute(text("SELECT COUNT(*) FROM news_users")).scalar() or 0
        total_news = conn.execute(text("SELECT COUNT(*) FROM news WHERE status='published'")).scalar() or 0
        total_views = conn.execute(text("SELECT COALESCE(SUM(view_count),0) FROM news WHERE status='published'")).scalar() or 0
        total_subs = conn.execute(text("SELECT COUNT(*) FROM subscriptions WHERE is_active=1 AND is_verified=1")).scalar() or 0

        by_category = [
            dict(row._mapping) for row in conn.execute(text("""
                SELECT c.name as category, COUNT(*) as count
                FROM news n
                JOIN categories c ON n.category_id = c.id
                WHERE n.status = 'published'
                GROUP BY c.name ORDER BY count DESC
            """))
        ]

        top_news = [
            dict(row._mapping) for row in conn.execute(text("""
                SELECT id, title, view_count, source
                FROM news WHERE status='published'
                ORDER BY view_count DESC LIMIT 5
            """))
        ]

        daily_news = [
            dict(row._mapping) for row in conn.execute(text("""
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM news WHERE status='published'
                  AND created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                GROUP BY day ORDER BY day
            """))
        ]

        # news_users에 created_at 컬럼 없음 — 빈 리스트
        daily_users = []

    return {
        "total_users": total_users,
        "total_news": total_news,
        "total_views": int(total_views),
        "total_subs": total_subs,
        "by_category": by_category,
        "top_news": top_news,
        "daily_news": [{"day": str(r["day"]), "count": r["count"]} for r in daily_news],
        "daily_users": [{"day": str(r["day"]), "count": r["count"]} for r in daily_users],
    }
