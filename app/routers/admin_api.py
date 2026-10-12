import uuid
import time
import threading
import html as _html
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx as _httpx
from fastapi import APIRouter, Depends, Request, UploadFile, File
from sqlalchemy import text

from app.database import engine
from app.auth import require_admin, require_admin_or_press
from app.config import public_base_url, settings
from app.services.email import send_newsletters_batch
from app.services.ai_summary import get_or_create_summary, summarize_articles
from app.services.naver_news import (
    fetch_and_save_news, extract_full_content, clean_article_text,
    CLIENT_ID, CLIENT_SECRET,
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
# 이미지 업로드는 기자 글쓰기 페이지에서도 사용
upload_router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin_or_press)])

# 뉴스레터 발송 상태 추적
_newsletter_status = {"running": False, "message": "", "success": None}


def _load_subscriber_articles() -> list[dict]:
    """구독자별 카테고리별로 최신 기사 5개씩 — 카테고리마다 별도 이메일 발송용.

    (구독자 × 카테고리)마다 쿼리하던 방식 대신, 윈도우 함수로 쿼리 3번에 처리.
    """
    with engine.connect() as conn:
        # 1) 발송 대상 (구독자, 카테고리) 목록
        targets = conn.execute(text("""
            SELECT s.email, cs.category_id, COALESCE(cs.is_global, 0) AS is_global,
                   c.name AS category_name
            FROM subscriptions s
            JOIN category_subscriptions cs ON cs.user_id = s.user_id
            JOIN categories c ON cs.category_id = c.id
            WHERE s.is_active = TRUE AND s.is_verified = 1
            ORDER BY s.email, c.name
        """)).fetchall()
        if not targets:
            return []

        # 2) 대상별로 아직 안 보낸 최신 기사 5개
        unsent = conn.execute(text("""
            WITH t AS (
                SELECT DISTINCT s.email, cs.category_id, COALESCE(cs.is_global, 0) AS t_global
                FROM subscriptions s
                JOIN category_subscriptions cs ON cs.user_id = s.user_id
                WHERE s.is_active = TRUE AND s.is_verified = 1
            ), ranked AS (
                SELECT t.email AS t_email, t.t_global, n.*, c.name AS category_name,
                       ROW_NUMBER() OVER (
                           PARTITION BY t.email, t.category_id, t.t_global
                           ORDER BY n.created_at DESC, n.id DESC
                       ) AS rn
                FROM t
                JOIN news n ON n.category_id = t.category_id
                           AND COALESCE(n.is_global, 0) = t.t_global
                           AND n.status = 'published'
                LEFT JOIN categories c ON n.category_id = c.id
                WHERE NOT EXISTS (
                    SELECT 1 FROM newsletter_sent ns
                    WHERE ns.email = t.email AND ns.news_id = n.id
                )
            )
            SELECT * FROM ranked WHERE rn <= 5 ORDER BY created_at DESC, id DESC
        """)).fetchall()

        # 3) 새 기사가 없을 때 재발송할 카테고리별 최근 5개
        latest = conn.execute(text("""
            SELECT * FROM (
                SELECT n.*, c.name AS category_name,
                       ROW_NUMBER() OVER (
                           PARTITION BY n.category_id, COALESCE(n.is_global, 0)
                           ORDER BY n.created_at DESC, n.id DESC
                       ) AS rn
                FROM news n
                LEFT JOIN categories c ON n.category_id = c.id
                WHERE n.status = 'published'
            ) x WHERE rn <= 5 ORDER BY created_at DESC, id DESC
        """)).fetchall()

    def _article(row) -> dict:
        d = dict(row._mapping)
        for k in ("t_email", "t_global", "rn"):
            d.pop(k, None)
        return d

    unsent_map: dict[tuple, list[dict]] = {}
    for r in unsent:
        unsent_map.setdefault((r.t_email, r.category_id, r.t_global), []).append(_article(r))
    latest_map: dict[tuple, list[dict]] = {}
    for r in latest:
        latest_map.setdefault((r.category_id, int(r.is_global or 0)), []).append(_article(r))

    result = []
    for t in targets:
        is_global_val = int(t.is_global or 0)
        articles = (unsent_map.get((t.email, t.category_id, is_global_val))
                    or latest_map.get((t.category_id, is_global_val)))
        if not articles:
            continue
        label = "해외" if is_global_val else "국내"
        result.append({
            "email": t.email,
            "category_name": f"{label}{t.category_name}",
            "articles": articles,
        })
    return result


def run_newsletter_job(base_url: str | None = None) -> dict:
    """뉴스레터 일괄 발송 — 스케줄러·외부 크론·API 엔드포인트 공용"""
    base_url = base_url or public_base_url()
    _newsletter_status["running"] = True
    _newsletter_status["message"] = "구독자 정보 불러오는 중..."
    _newsletter_status["success"] = None

    try:
        # 1) DB 읽기
        subscriber_data = _load_subscriber_articles()
        if not subscriber_data:
            _newsletter_status.update(running=False, success=False, message="구독자가 없습니다.")
            return {"success": False, "message": "구독자가 없습니다."}

        # 2) 발송할 기사만 AI 요약 생성 후 이메일 발송
        unique = {a["id"]: a for sub in subscriber_data for a in sub["articles"]}
        _newsletter_status["message"] = f"AI 요약 생성 중... (기사 {len(unique)}건)"
        summarized = {a["id"]: a for a in summarize_articles(list(unique.values()))}
        items = [
            {
                "email": sub["email"],
                "articles": [summarized[a["id"]] for a in sub["articles"]],
                "category_name": sub.get("category_name", ""),
            }
            for sub in subscriber_data
        ]
        _newsletter_status["message"] = f"이메일 발송 중... (총 {len(subscriber_data)}건)"
        results = send_newsletters_batch(items, base_url=base_url)

        total_sent = 0
        sent_log: list[dict] = []
        for sub_info, item, success in zip(subscriber_data, items, results):
            cat = sub_info.get("category_name", "")
            if success:
                total_sent += 1
                print(f"[뉴스레터] 발송 완료: {sub_info['email']} [{cat}]")
                for a in item["articles"]:
                    if a.get("id"):
                        sent_log.append({"email": sub_info["email"], "news_id": a["id"]})
            else:
                print(f"[뉴스레터] 발송 실패: {sub_info['email']} [{cat}]")

        # newsletter_sent 배치 INSERT
        if sent_log:
            with engine.connect() as conn:
                conn.execute(
                    text("INSERT INTO newsletter_sent (email, news_id) VALUES (:email, :news_id) ON CONFLICT DO NOTHING"),
                    sent_log,
                )
                conn.commit()

        msg = f"총 {total_sent}건 발송 완료!"
        _newsletter_status.update(running=False, success=True, message=msg)
        print(f"[뉴스레터] {msg}")
        return {"success": True, "message": msg}

    except Exception as e:
        _newsletter_status.update(running=False, success=False, message=f"오류 발생: {e}")
        return {"success": False, "message": str(e)}


@router.post("/send-newsletter")
def send_newsletter_api(request: Request):
    if _newsletter_status["running"]:
        return {"success": False, "message": "이미 발송 중입니다. 잠시 후 다시 시도해주세요."}
    base_url = public_base_url()
    threading.Thread(target=run_newsletter_job, args=(base_url,), daemon=True).start()
    return {"success": True, "message": "뉴스레터 발송을 시작했습니다. AI 요약 생성 후 순차 발송됩니다."}


@router.get("/newsletter-status")
def newsletter_status():
    return _newsletter_status

@router.post("/fetch-news")
def fetch_news_api():
    try:
        count = fetch_and_save_news()
        return {"success": True, "message": f"{count}개 뉴스를 가져왔습니다!"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/fetch-global-news")
def fetch_global_news_api():
    try:
        from app.services.global_news import fetch_and_save_global_news
        count = fetch_and_save_global_news()
        return {"success": True, "message": f"해외뉴스 {count}개를 가져왔습니다!"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/recrawl-content")
def recrawl_content_api():
    # 1) DB 연결은 짧게 — 처리할 목록만 로딩 후 즉시 닫기
    with engine.connect() as conn:
        # 요청 시간 제한에 걸리지 않도록 한 번에 100건씩
        rows = conn.execute(
            text("""
                SELECT id, link, naver_link, content FROM news
                WHERE (content IS NULL OR LENGTH(content) < 1000)
                  AND (COALESCE(TRIM(naver_link), '') != '' OR COALESCE(TRIM(link), '') != '')
                ORDER BY id DESC
                LIMIT 100
            """)
        ).fetchall()
    todo = [
        (r.id, (r.naver_link or "").strip() or (r.link or "").strip(), r.content)
        for r in rows
    ]

    # 2) HTTP 스크래핑 (DB 연결 없이) — 병렬
    with ThreadPoolExecutor(max_workers=10) as ex:
        contents = list(ex.map(lambda t: extract_full_content(t[1]), todo))

    updates = [
        {"content": new_content, "id": article_id}
        for (article_id, _, old_content), new_content in zip(todo, contents)
        if new_content and len(new_content) > len(old_content or "")
    ]
    failed = len(todo) - len(updates)

    # 3) 일괄 업데이트
    if updates:
        with engine.connect() as conn:
            conn.execute(text("UPDATE news SET content = :content WHERE id = :id"), updates)
            conn.commit()

    updated = len(updates)
    return {"success": True, "message": f"본문 업데이트: {updated}건 성공, {failed}건 실패 (100건씩 처리, 반복 실행 가능)"}


@router.post("/fix-content-via-api")
def _norm_title(t: str) -> str:
    """네이버 검색 결과 제목과 DB 제목을 비교하기 좋게 정리 (태그·HTML 엔티티·공백 차이 제거)"""
    t = _html.unescape(re.sub(r"<[^>]+>", "", t or ""))
    return re.sub(r"\s+", "", t).strip()


# 이번 서버 실행 중에 이미 시도했다가 못 찾은 기사 — 다시 눌렀을 때 같은 100건만 반복하지 않게 건너뛴다
_api_tried_ids: set[int] = set()


def fix_content_via_api():
    """네이버 API로 기사 제목 검색 → naver_link 복원 → 본문 재수집"""
    if not CLIENT_ID or not CLIENT_SECRET:
        return {"success": False, "message": "네이버 API 키(NAVER_CLIENT_ID · NAVER_CLIENT_SECRET)가 설정되지 않았습니다."}

    naver_headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }

    # 1) 처리 목록 로딩 — 네이버에서 수집한 국내 기사만 대상
    #    (해외뉴스·언론사가 직접 쓴 기사는 네이버 검색에 없으므로 제외)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, title, content FROM news
            WHERE (content IS NULL OR LENGTH(content) < 500)
              AND (naver_link IS NULL OR naver_link = '')
              AND COALESCE(is_global, 0) = 0
              AND author_id IS NULL
            ORDER BY id DESC
            LIMIT 1000
        """)).fetchall()
    todo = [r for r in rows if r.id not in _api_tried_ids][:100]
    if not todo:
        return {"success": True, "message": "복원할 기사가 없습니다. (네이버에서 수집한 국내 기사 중 본문이 짧은 기사 기준)"}

    stats = {"api_error": 0, "not_found": 0, "extract_fail": 0}

    # 2) HTTP 작업 (DB 연결 없이) — 네이버 API 호출 제한을 고려해 4개씩 병렬
    def _restore(row):
        query = urllib.parse.quote(row.title[:50])
        api_url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=10&sort=sim"
        try:
            with _httpx.Client(timeout=5) as client:
                res = client.get(api_url, headers=naver_headers)
            time.sleep(0.1)
            if res.status_code != 200:
                stats["api_error"] += 1
                return None

            target = _norm_title(row.title)
            naver_link = None
            for item in res.json().get("items", []):
                if _norm_title(item.get("title", "")) == target and item.get("link"):
                    naver_link = item["link"]
                    break
            if not naver_link:
                stats["not_found"] += 1
                return None

            content = extract_full_content(naver_link)
            if content and len(content) > len(row.content or ""):
                return {"c": content, "nl": naver_link, "id": row.id}
            stats["extract_fail"] += 1
        except Exception:
            stats["api_error"] += 1
        return None

    with ThreadPoolExecutor(max_workers=4) as ex:
        updates = [u for u in ex.map(_restore, todo) if u]
    _api_tried_ids.update(r.id for r in todo)

    # 3) 일괄 업데이트
    if updates:
        with engine.connect() as conn:
            conn.execute(text("UPDATE news SET content=:c, naver_link=:nl WHERE id=:id"), updates)
            conn.commit()

    updated = len(updates)
    detail = f"검색 결과 없음 {stats['not_found']} · 본문 추출 실패 {stats['extract_fail']} · API 오류 {stats['api_error']}"
    if stats["api_error"] and not updated and stats["api_error"] >= len(todo) // 2:
        detail += " — 네이버 API 키나 하루 호출 한도를 확인해주세요"
    return {"success": True, "message": f"API 재수집: {updated}건 성공 / {len(todo)}건 시도 ({detail}). 다시 누르면 다음 기사로 넘어갑니다."}


@router.post("/clean-content")
def clean_content_api():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, content FROM news WHERE content IS NOT NULL")).fetchall()
        updates = []
        for row in rows:
            fixed = clean_article_text(row.content)
            if fixed != row.content:
                updates.append({"content": fixed, "id": row.id})
        if updates:
            conn.execute(text("UPDATE news SET content = :content WHERE id = :id"), updates)
            conn.commit()
    return {"success": True, "message": f"{len(updates)}건의 기사에서 JS 코드를 제거했습니다."}


@upload_router.post("/upload-image")
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
                   STRING_AGG(c.name, ', ' ORDER BY c.name) AS categories
            FROM subscriptions s
            LEFT JOIN news_users u ON s.user_id = u.id
            LEFT JOIN category_subscriptions cs ON cs.user_id = s.user_id
            LEFT JOIN categories c ON cs.category_id = c.id
            GROUP BY s.id, s.user_id, u.name, s.email, s.is_active, s.is_verified, s.created_at
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


@router.post("/reports/{report_id}/delete-post")
def delete_reported_post(report_id: int):
    """신고된 기사 삭제 + 신고 처리완료"""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT news_id FROM reports WHERE id=:id"),
            {"id": report_id}
        ).fetchone()
        if row and row.news_id:
            conn.execute(text("DELETE FROM news WHERE id=:id"), {"id": row.news_id})
        conn.execute(
            text("UPDATE reports SET status='deleted' WHERE id=:id"),
            {"id": report_id}
        )
        conn.commit()
    return {"success": True}


@router.get("/press-members")
def get_press_members():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, name, email, tel, created_at, press_approved
            FROM news_users
            WHERE role = 'press'
            ORDER BY press_approved ASC, created_at DESC
        """)).fetchall()
    result = []
    for row in rows:
        d = dict(row._mapping)
        if d["created_at"]:
            d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M")
        result.append(d)
    return result


@router.post("/press/{user_id}/approve")
def approve_press(user_id: str):
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE news_users SET press_approved = 1 WHERE id = :id AND role = 'press'"),
            {"id": user_id}
        )
        conn.commit()
    return {"success": True}


@router.post("/press/{user_id}/reject")
def reject_press(user_id: str):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM news WHERE author_id = :id"), {"id": user_id})
        conn.execute(text("DELETE FROM news_users WHERE id = :id AND role = 'press'"), {"id": user_id})
        conn.commit()
    return {"success": True}


@router.get("/stats")
def get_stats():
    with engine.connect() as conn:
        total_users = conn.execute(text("SELECT COUNT(*) FROM news_users")).scalar() or 0
        total_news = conn.execute(text("SELECT COUNT(*) FROM news WHERE status='published'")).scalar() or 0
        total_views = conn.execute(text("SELECT COALESCE(SUM(view_count),0) FROM news WHERE status='published'")).scalar() or 0
        total_subs = conn.execute(text("SELECT COUNT(*) FROM subscriptions WHERE is_active=TRUE AND is_verified=1")).scalar() or 0

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
                  AND created_at >= CURRENT_DATE - INTERVAL '6 days'
                GROUP BY day ORDER BY day
            """))
        ]

        daily_users = [
            dict(row._mapping) for row in conn.execute(text("""
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM news_users
                WHERE created_at IS NOT NULL
                  AND created_at >= CURRENT_DATE - INTERVAL '6 days'
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
