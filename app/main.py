from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers.pages import router as pages_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="News Delivery MVP")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(pages_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
