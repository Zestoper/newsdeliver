from sqlalchemy import text
from app.database import engine

subscriptions = []


def get_news_items() -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM news WHERE status = 'published' ORDER BY created_at ASC")
        )
        return [dict(row._mapping) for row in result]


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