from sqlalchemy import text
from app.database import engine

news_items = [
    {
        "title": "아침 브리핑: 오늘의 주요 헤드라인",
        "summary": "하루를 빠르게 시작할 수 있도록 핵심 뉴스만 간단하게 정리했습니다.",
        "category": "Daily Brief",
    },
    {
        "title": "IT 트렌드: 생성형 AI 서비스 경쟁 심화",
        "summary": "기업들이 생산성과 개인화 기능을 강화하며 새로운 사용자 경험을 내놓고 있습니다.",
        "category": "Technology",
    },
    {
        "title": "라이프: 주말에 읽기 좋은 문화 뉴스 모음",
        "summary": "영화, 전시, 도서 소식을 한 번에 볼 수 있는 큐레이션 콘텐츠입니다.",
        "category": "Culture",
    },
]

subscriptions = []


def get_news_items() -> list[dict]:
    return news_items


def is_duplicate_user(*, user_id: str, email: str) -> dict:
    with engine.connect() as conn:
        id_result = conn.execute(
            text("SELECT id FROM news_users WHERE id = :id"),
            {"id": user_id}
        )
        email_result = conn.execute(
            text("SELECT id FROM news_users WHERE email = :email"),
            {"email": email}
        )
        return {
            "id": id_result.fetchone() is not None,
            "email": email_result.fetchone() is not None,
        }


def add_user(user: dict) -> None:
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO news_users (id, name, birth, pw, email, tel)
                VALUES (:id, :name, :birth, :pw, :email, :tel)
            """),
            {
                "id": user["user_id"],
                "name": user["name"],
                "birth": user["birth"],
                "pw": user["password"],
                "email": user["email"],
                "tel": user["phone"],
            }
        )
        conn.commit()


def get_user(*, user_id: str, password: str) -> dict | None:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM news_users WHERE id = :id AND pw = :pw"),
            {"id": user_id, "pw": password}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None


def is_duplicate_subscription(email: str) -> bool:
    return email in subscriptions


def add_subscription(email: str) -> None:
    subscriptions.append(email)