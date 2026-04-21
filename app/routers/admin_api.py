from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine
from app.services.email import send_newsletter

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/send-newsletter")
def send_newsletter_api():
    with engine.connect() as conn:
        # 구독자 목록
        subs = conn.execute(
            text("SELECT user_id, email FROM subscriptions WHERE is_active = 1")
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
                    category_name=news.get("category_name", "")
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