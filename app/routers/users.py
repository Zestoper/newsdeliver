from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    tel: Optional[str] = None
    role: Optional[str] = None


# 전체 조회
@router.get("")
def get_users(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT id, name, birth, email, tel, role FROM news_users"))
    return [dict(row._mapping) for row in result]


# 수정
@router.put("/{user_id}")
def update_user(user_id: str, data: UserUpdate, db: Session = Depends(get_db)):
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["user_id"] = user_id
    db.execute(text(f"UPDATE news_users SET {set_clause} WHERE id = :user_id"), fields)
    db.commit()
    return {"message": "수정 완료"}


# 삭제
@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM news_users WHERE id = :id"), {"id": user_id})
    db.commit()
    return {"message": "삭제 완료"}