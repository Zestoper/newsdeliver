from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine
from app.services.email import send_newsletter

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/send-newsletter")
def send_newsletter_api():
    with engine.connect() as conn:
        # 최신 발행 뉴스 1개
        news_result = conn.execute(
            text("SELECT * FROM news WHERE status = 'published' ORDER BY created_at DESC LIMIT 1")
        )
        news = news_result.fetchone()
        if not news:
            return {"success": False, "message": "발행된 뉴스가 없습니다."}
        news = dict(news._mapping)

        # 구독자 이메일 목록
        sub_result = conn.execute(
            text("SELECT email FROM subscriptions WHERE is_active = 1")
        )
        emails = [row.email for row in sub_result]

        if not emails:
            return {"success": False, "message": "구독자가 없습니다."}

    count = send_newsletter(
        to_emails=emails,
        title=news["title"],
        content=news["content"],
        source=news.get("source", "")
    )

    # 발송 로그 저장
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO email_logs (news_id, recipient_count) VALUES (:news_id, :count)"),
            {"news_id": news["id"], "count": count}
        )
        conn.commit()

    return {"success": True, "message": f"{count}명에게 발송 완료!"}