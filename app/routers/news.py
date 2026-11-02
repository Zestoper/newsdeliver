from fastapi import APIRouter, Depends
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime, time, timedelta
from app.database import engine
from app.auth import require_admin

router = APIRouter(prefix="/api/news", tags=["news"], dependencies=[Depends(require_admin)])


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


# created_at 은 DB 세션 시간대(운영은 UTC) 기준 TIMESTAMP 라서 한국 시간으로 바꿔서 쓴다.
# (timestamp AT TIME ZONE 세션시간대 → timestamptz → AT TIME ZONE 'Asia/Seoul' → 한국 시각)
_KST_CREATED = "((created_at AT TIME ZONE current_setting('TimeZone')) AT TIME ZONE 'Asia/Seoul')"
ADMIN_NEWS_LIMIT = 5000


@router.get("")
def get_news(
    is_global: Optional[int] = None,
    date_from: Optional[date] = None,   # 한국 날짜 (포함)
    date_to: Optional[date] = None,     # 한국 날짜 (포함)
):
    """관리자 뉴스 목록.

    전체 기사가 5만 건이 넘어서 최신 5000건만 내려주면 열흘쯤 지난 날짜는 아예 안 보였다.
    날짜를 고르면 DB에서 그 기간을 직접 조회한다.
    """
    where, params = ["1=1"], {"limit": ADMIN_NEWS_LIMIT}
    if is_global is not None:
        where.append("COALESCE(is_global, 0) = :g")
        params["g"] = 1 if is_global else 0
    if date_from:
        where.append(f"{_KST_CREATED} >= :d_from")
        params["d_from"] = datetime.combine(date_from, time.min)
    if date_to:
        where.append(f"{_KST_CREATED} < :d_to")
        params["d_to"] = datetime.combine(date_to + timedelta(days=1), time.min)
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT id, title, source, status, category_id, image_url, is_global,
                   {_KST_CREATED} AS created_at
            FROM news WHERE {' AND '.join(where)}
            ORDER BY created_at DESC LIMIT :limit
        """), params)
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