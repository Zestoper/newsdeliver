from fastapi import APIRouter
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.database import engine

router = APIRouter(prefix="/api/news", tags=["news"])


class NewsCreate(BaseModel):
    title: str
    content: str
    image_url: Optional[str] = ""
    source: Optional[str] = ""
    status: Optional[str] = "draft"
    category_id: Optional[int] = None


class NewsUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    category_id: Optional[int] = None


@router.get("")
def get_news():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, title, source, status, category_id, image_url, is_global, created_at
            FROM news ORDER BY created_at DESC LIMIT 300
        """))
        return [dict(row._mapping) for row in result]


@router.get("/{news_id}")
def get_news_one(news_id: int):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM news WHERE id = :id"), {"id": news_id}
        ).fetchone()
        if not row:
            return {}
        return dict(row._mapping)


@router.post("")
def create_news(data: NewsCreate):
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO news (title, content, image_url, source, status, category_id)
                VALUES (:title, :content, :image_url, :source, :status, :category_id)
            """),
            data.dict()
        )
        conn.commit()
    return {"message": "등록 완료"}


@router.put("/{news_id}")
def update_news(news_id: int, data: NewsUpdate):
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if not fields:
        return {"message": "수정할 항목 없음"}
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["news_id"] = news_id
    with engine.connect() as conn:
        conn.execute(text(f"UPDATE news SET {set_clause} WHERE id = :news_id"), fields)
        conn.commit()
    return {"message": "수정 완료"}


@router.delete("/{news_id}")
def delete_news(news_id: int):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM news WHERE id = :id"), {"id": news_id})
        conn.commit()
    return {"message": "삭제 완료"}