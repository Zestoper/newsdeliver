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
            ("ALTER TABLE subscriptions ADD COLUMN is_verified TINYINT(1) DEFAULT 0", "subscriptions.is_verified"),
            ("ALTER TABLE subscriptions ADD COLUMN verify_token VARCHAR(100)", "subscriptions.verify_token"),
            ("ALTER TABLE subscriptions DROP INDEX unique_email", "subscriptions.unique_email 제약 제거"),
        ]
        for sql, col in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ {col}")
            except Exception:
                pass  # 이미 처리됨
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