from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.routers.pages import router as pages_router
from app.routers.users import router as users_router
from app.routers.news import router as news_router
from app.routers.press import router as press_router
from app.routers.admin_api import router as admin_api_router

BASE_DIR = Path(__file__).resolve().parent

try:
    with engine.connect() as conn:
        print("✅ DB 연결 성공!")
        from sqlalchemy import text
        migrations = [
            ("ALTER TABLE news ADD COLUMN link VARCHAR(500)", "news.link"),
            ("ALTER TABLE news ADD COLUMN view_count INT DEFAULT 0", "news.view_count"),
            ("ALTER TABLE subscriptions ADD COLUMN is_verified TINYINT(1) DEFAULT 0", "subscriptions.is_verified"),
            ("ALTER TABLE subscriptions ADD COLUMN verify_token VARCHAR(100)", "subscriptions.verify_token"),
            ("ALTER TABLE subscriptions DROP INDEX unique_email", "subscriptions.unique_email 제약 제거"),
            ("ALTER TABLE news_comments ADD COLUMN parent_id INT DEFAULT NULL", "news_comments.parent_id"),
        ]
        # reports 테이블 생성
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    news_id INT NOT NULL,
                    reporter_id VARCHAR(50) NOT NULL,
                    reporter_name VARCHAR(100) NOT NULL,
                    reason VARCHAR(500) DEFAULT '',
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            print("✅ reports 테이블")
        except Exception:
            pass

        # bookmarks 테이블 생성
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    news_id INT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_bookmark (user_id, news_id)
                )
            """))
            conn.commit()
            print("✅ bookmarks 테이블")
        except Exception:
            pass

        # comment_likes 테이블 생성 (없을 때만)
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS comment_likes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    comment_id INT NOT NULL,
                    user_id VARCHAR(50) NOT NULL,
                    UNIQUE KEY unique_comment_like (comment_id, user_id)
                )
            """))
            conn.commit()
            print("✅ comment_likes 테이블")
        except Exception:
            pass
        # news.title 중복 방지 UNIQUE 인덱스
        try:
            conn.execute(text("ALTER TABLE news ADD UNIQUE INDEX unique_title (title(191))"))
            conn.commit()
            print("✅ news.title unique index")
        except Exception:
            pass

        for sql, col in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ {col}")
            except Exception:
                pass  # 이미 처리됨

        # 새 카테고리 추가
        new_cats = ["연예", "국제", "사회"]
        for cat in new_cats:
            try:
                conn.execute(text("INSERT IGNORE INTO categories (name) VALUES (:name)"), {"name": cat})
                conn.commit()
                print(f"✅ 카테고리 추가: {cat}")
            except Exception:
                pass
except Exception as e:
    print(f"❌ DB 연결 실패: {e}")

app = FastAPI(title="News Delivery MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(pages_router)
app.include_router(users_router)
app.include_router(news_router)
app.include_router(press_router)
app.include_router(admin_api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)