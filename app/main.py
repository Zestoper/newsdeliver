from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.database import engine
from app.routers.pages import router as pages_router
from app.routers.users import router as users_router
from app.routers.news import router as news_router
from app.routers.press import router as press_router
from app.routers.admin_api import router as admin_api_router
from app.routers.oauth import router as oauth_router
from app.routers.chat import router as chat_router

BASE_DIR = Path(__file__).resolve().parent

try:
    with engine.connect() as conn:
        print("✅ DB 연결 성공!")
        from sqlalchemy import text
        migrations = [
            ("ALTER TABLE news ADD COLUMN link VARCHAR(500)", "news.link"),
            ("ALTER TABLE news ADD COLUMN naver_link VARCHAR(500)", "news.naver_link"),
            ("ALTER TABLE news ADD COLUMN view_count INT DEFAULT 0", "news.view_count"),
            ("ALTER TABLE subscriptions ADD COLUMN is_verified TINYINT(1) DEFAULT 0", "subscriptions.is_verified"),
            ("ALTER TABLE subscriptions ADD COLUMN verify_token VARCHAR(100)", "subscriptions.verify_token"),
            ("ALTER TABLE subscriptions DROP INDEX unique_email", "subscriptions.unique_email 제약 제거"),
            ("ALTER TABLE news_comments ADD COLUMN parent_id INT DEFAULT NULL", "news_comments.parent_id"),
            ("ALTER TABLE news_users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP", "news_users.created_at"),
            ("ALTER TABLE news ADD COLUMN ai_summary TEXT NULL", "news.ai_summary"),
            ("ALTER TABLE chat_messages ADD COLUMN message_type VARCHAR(10) DEFAULT 'text'", "chat_messages.message_type"),
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

        # 소셜 로그인용 컬럼 추가 및 pw NULL 허용
        oauth_migrations = [
            ("ALTER TABLE news_users MODIFY pw VARCHAR(255) NULL", "news_users.pw nullable"),
            ("ALTER TABLE news_users ADD COLUMN oauth_provider VARCHAR(20) NULL", "news_users.oauth_provider"),
            ("ALTER TABLE news_users ADD COLUMN oauth_id VARCHAR(100) NULL", "news_users.oauth_id"),
            ("ALTER TABLE news_users ADD UNIQUE KEY oauth_unique (oauth_provider, oauth_id)", "news_users.oauth_unique"),
        ]
        for sql, col in oauth_migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ {col}")
            except Exception:
                pass

        for sql, col in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ {col}")
            except Exception:
                pass  # 이미 처리됨

        # chat 테이블 생성
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_rooms (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    user_name VARCHAR(100),
                    last_message_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user (user_id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    room_id INT NOT NULL,
                    sender VARCHAR(10) NOT NULL,
                    message TEXT NOT NULL,
                    is_read TINYINT(1) DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            print("✅ chat 테이블")
        except Exception:
            pass

        # newsletter_sent 테이블 생성
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS newsletter_sent (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    news_id INT NOT NULL,
                    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_sent (email, news_id)
                )
            """))
            conn.commit()
            print("✅ newsletter_sent 테이블")
        except Exception:
            pass

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

KST = pytz.timezone("Asia/Seoul")

def _newsletter_job():
    from app.routers.admin_api import run_newsletter_job
    run_newsletter_job(base_url="http://127.0.0.1:8000")

def _fetch_news_job():
    from app.services.naver_news import fetch_and_save_news
    try:
        count = fetch_and_save_news()
        print(f"[뉴스 자동수집] {count}개 저장")
    except Exception as e:
        print(f"[뉴스 자동수집] 실패: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    threading.Thread(target=_fetch_news_job, daemon=True).start()
    print("✅ 서버 시작 시 뉴스 수집 중...")

    scheduler = BackgroundScheduler(timezone=KST)
    scheduler.add_job(_newsletter_job, CronTrigger(hour=7,  minute=30, timezone=KST))
    scheduler.add_job(_newsletter_job, CronTrigger(hour=18, minute=30, timezone=KST))
    scheduler.add_job(_fetch_news_job,  CronTrigger(hour="*/2", minute=0, timezone=KST))
    scheduler.start()
    print("✅ 뉴스레터 스케줄러 시작 (07:30, 18:30 KST)")
    print("✅ 뉴스 자동수집 스케줄러 시작 (2시간마다)")
    yield
    scheduler.shutdown()
    print("스케줄러 종료")

app = FastAPI(title="News Delivery MVP", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(oauth_router)
app.include_router(pages_router)
app.include_router(users_router)
app.include_router(news_router)
app.include_router(press_router)
app.include_router(admin_api_router)
app.include_router(chat_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)