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

import time
import urllib.parse
import httpx as _httpx
from app.services.naver_news import (
    fetch_and_save_news, extract_full_content, clean_article_text,
    CLIENT_ID, CLIENT_SECRET,
)

@router.post("/fetch-news")
def fetch_news_api():
    try:
        count = fetch_and_save_news()
        return {"success": True, "message": f"{count}개 뉴스를 가져왔습니다!"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/recrawl-content")
def recrawl_content_api():
    # 1) DB 연결은 짧게 — 처리할 목록만 로딩 후 즉시 닫기
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, link, naver_link, content FROM news
                WHERE (naver_link IS NOT NULL AND naver_link != '')
                   OR (link IS NOT NULL AND link != '')
                ORDER BY id DESC
            """)
        ).fetchall()
    todo = [
        (r.id, (r.naver_link or "").strip() or (r.link or "").strip(), r.content)
        for r in rows
        if not (r.content and len(r.content) >= 1000)
        and ((r.naver_link or "").strip() or (r.link or "").strip())
    ]
    skipped = len(rows) - len(todo)

    # 2) HTTP 스크래핑 (DB 연결 없이)
    updates = []
    failed = 0
    for article_id, crawl_url, old_content in todo:
        new_content = extract_full_content(crawl_url)
        if new_content and len(new_content) > len(old_content or ""):
            updates.append((article_id, new_content))
        else:
            failed += 1

    # 3) 업데이트는 건별로 커밋 — 락 최소화
    with engine.connect() as conn:
        for article_id, new_content in updates:
            conn.execute(
                text("UPDATE news SET content = :content WHERE id = :id"),
                {"content": new_content, "id": article_id}
            )
            conn.commit()

    updated = len(updates)
    return {"success": True, "message": f"본문 업데이트: {updated}건 성공, {failed}건 실패 (충분한 본문: {skipped}건)"}


@router.post("/fix-content-via-api")
def fix_content_via_api():
    """네이버 API로 기사 제목 검색 → naver_link 복원 → 본문 재수집"""
    naver_headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }

    # 1) 처리 목록 로딩 후 DB 연결 닫기
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, title, content FROM news
            WHERE (content IS NULL OR LENGTH(content) < 500)
            AND (naver_link IS NULL OR naver_link = '')
            ORDER BY id DESC
            LIMIT 100
        """)).fetchall()
    todo = list(rows)

    # 2) HTTP 작업 (DB 연결 없이)
    updates = []
    failed = 0
    for row in todo:
        query = urllib.parse.quote(row.title[:50])
        api_url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=3&sort=date"
        try:
            with _httpx.Client(timeout=5) as client:
                res = client.get(api_url, headers=naver_headers)
            if res.status_code != 200:
                failed += 1
                time.sleep(0.1)
                continue

            naver_link = None
            for item in res.json().get("items", []):
                item_title = (item.get("title", "")
                              .replace("<b>", "").replace("</b>", "")
                              .replace("&quot;", '"').replace("&amp;", "&"))
                if item_title.strip() == row.title.strip():
                    naver_link = item.get("link", "")
                    break

            if naver_link:
                content = extract_full_content(naver_link)
                if content and len(content) > len(row.content or ""):
                    updates.append((row.id, content, naver_link))
                else:
                    failed += 1
            else:
                failed += 1

            time.sleep(0.1)
        except Exception:
            failed += 1

    # 3) 건별 커밋
    with engine.connect() as conn:
        for article_id, content, naver_link in updates:
            conn.execute(
                text("UPDATE news SET content=:c, naver_link=:nl WHERE id=:id"),
                {"c": content, "nl": naver_link, "id": article_id}
            )
            conn.commit()

    updated = len(updates)
    return {"success": True, "message": f"API 재수집: {updated}건 성공, {failed}건 실패 (100건씩 처리, 반복 실행 가능)"}


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

        daily_users = [
            dict(row._mapping) for row in conn.execute(text("""
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM news_users
                WHERE created_at IS NOT NULL
                  AND created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                GROUP BY day ORDER BY day
            """))
        ]

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
