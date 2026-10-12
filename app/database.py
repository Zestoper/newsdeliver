from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

def _normalize_db_url(url: str) -> str:
    # SQLAlchemy 2.1부터 "postgresql://"의 기본 드라이버가 psycopg(v3)로 바뀌었다.
    # requirements에는 psycopg2-binary만 있으므로 드라이버를 명시해서 고정한다.
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


engine = create_engine(_normalize_db_url(settings.DB_URL), isolation_level="READ COMMITTED")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()