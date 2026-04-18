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


class NewsUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None


# 전체 조회
@router.get("")
def get_news():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM news ORDER BY created_at DESC"))
        return [dict(row._mapping) for row in result]


# 추가
@router.post("")
def create_news(data: NewsCreate):
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO news (title, content, image_url, source, status)
                VALUES (:title, :content, :image_url, :source, :status)
            """),
            data.dict()
        )
        conn.commit()
    return {"message": "등록 완료"}


# 수정
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


# 삭제
@router.delete("/{news_id}")
def delete_news(news_id: int):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM news WHERE id = :id"), {"id": news_id})
        conn.commit()
    return {"message": "삭제 완료"}