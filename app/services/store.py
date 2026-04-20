from sqlalchemy import text
from app.database import engine


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


def is_duplicate_subscription(email: str, user_id: str = None) -> bool:
    with engine.connect() as conn:
        if user_id:
            result = conn.execute(
                text("SELECT id FROM subscriptions WHERE user_id = :user_id AND is_active = 1"),
                {"user_id": user_id}
            )
        else:
            result = conn.execute(
                text("SELECT id FROM subscriptions WHERE email = :email AND is_active = 1"),
                {"email": email}
            )
        return result.fetchone() is not None


def add_subscription(email: str, user_id: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO subscriptions (user_id, email, is_active) VALUES (:user_id, :email, 1)"),
            {"user_id": user_id, "email": email}
        )
        conn.commit()