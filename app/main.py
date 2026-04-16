from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.routers.pages import router as pages_router
from app.routers.users import router as users_router

BASE_DIR = Path(__file__).resolve().parent

try:
    with engine.connect() as conn:
        print("✅ DB 연결 성공!")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)