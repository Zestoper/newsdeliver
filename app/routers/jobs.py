"""외부 크론이 호출하는 예약 작업 엔드포인트.

Render 무료 플랜은 15분 동안 요청이 없으면 서버가 잠들기 때문에
서버 안의 APScheduler는 잠든 동안 실행되지 않는다.
대신 cron-job.org 같은 외부 크론이 정해진 시간에 이 엔드포인트를 호출하면
서버가 깨어나서 작업을 실행한다.

호출 예시
  POST https://<서버>/internal/jobs/newsletter
  헤더  X-Cron-Secret: <CRON_SECRET>
"""
import hmac
import threading

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import public_base_url, settings

router = APIRouter(prefix="/internal/jobs", tags=["jobs"])

_running: dict[str, bool] = {"fetch-news": False}


def _check_secret(header_secret: str | None, query_secret: str | None) -> None:
    expected = settings.CRON_SECRET
    given = header_secret or query_secret or ""
    if not expected or not hmac.compare_digest(given, expected):
        raise HTTPException(status_code=403, detail="forbidden")


@router.post("/newsletter", status_code=202)
def run_newsletter(
    x_cron_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
):
    _check_secret(x_cron_secret, secret)
    from app.routers.admin_api import _newsletter_status, run_newsletter_job
    if _newsletter_status.get("running"):
        return {"started": False, "message": "이미 발송 중입니다."}
    threading.Thread(target=run_newsletter_job, args=(public_base_url(),), daemon=True).start()
    return {"started": True, "message": "뉴스레터 발송을 시작했습니다."}


@router.post("/fetch-news", status_code=202)
def run_fetch_news(
    x_cron_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
):
    _check_secret(x_cron_secret, secret)
    if _running["fetch-news"]:
        return {"started": False, "message": "이미 수집 중입니다."}

    def _job():
        from app.main import _fetch_news_job
        _running["fetch-news"] = True
        try:
            _fetch_news_job()
        finally:
            _running["fetch-news"] = False

    threading.Thread(target=_job, daemon=True).start()
    return {"started": True, "message": "뉴스 수집을 시작했습니다."}
