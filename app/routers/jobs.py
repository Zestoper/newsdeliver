"""예약 작업 — 외부 크론 + 깨어날 때 밀린 작업 처리.

Render 무료 플랜은 15분 동안 요청이 없으면 서버가 잠들고, 깨어나는 데 50초 정도 걸린다.
cron-job.org 무료 요청은 30초면 끊기기 때문에 잠든 서버를 부르면 요청 자체는 실패할 수 있다.
그래서 요청이 성공했는지와 상관없이 **서버가 깨어나기만 하면** 밀린 작업을 처리한다.

  - 뉴스 수집: 30분 구간마다 한 번 (같은 구간에 여러 번 깨어나도 한 번만)
  - 뉴스레터: 07:30 · 18:30 발송 — 그 뒤 3시간 안에 처음 깨어날 때 한 번만 보낸다

"한 번만"은 DB의 job_state 테이블에 구간 키를 먼저 넣는 쪽만 실행하는 방식으로 보장한다.
(서버가 여러 번 깨어나거나 크론과 방문자가 동시에 깨워도 중복 실행되지 않음)

호출 예시
  POST https://<서버>/internal/jobs/fetch-news   헤더 X-Cron-Secret: <CRON_SECRET>
"""
import hmac
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text

from app.config import public_base_url, settings
from app.database import engine

router = APIRouter(prefix="/internal/jobs", tags=["jobs"])

KST = ZoneInfo("Asia/Seoul")
NEWSLETTER_SLOTS = ((7, 30), (18, 30))  # 발송 시각 (KST)
NEWSLETTER_CATCHUP = timedelta(hours=3)  # 발송 시각을 놓쳤을 때 이 시간 안에 깨어나면 보낸다

_lock = threading.Lock()
_running = False


def _check_secret(header_secret: str | None, query_secret: str | None) -> None:
    expected = settings.CRON_SECRET
    given = header_secret or query_secret or ""
    if not expected or not hmac.compare_digest(given, expected):
        raise HTTPException(status_code=403, detail="forbidden")


def _claim(key: str) -> bool:
    """이 키로 처음 실행하는 쪽이면 True. 이미 누가 실행했으면 False."""
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS job_state ("
            " key VARCHAR(100) PRIMARY KEY,"
            " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        ))
        row = conn.execute(
            text("INSERT INTO job_state (key) VALUES (:k) ON CONFLICT DO NOTHING RETURNING key"),
            {"k": key},
        ).fetchone()
        conn.commit()
    return row is not None


def _fetch_key(now: datetime) -> str:
    half = "00" if now.minute < 30 else "30"
    return f"fetch:{now:%Y-%m-%d-%H}{half}"


def _due_newsletter_key(now: datetime) -> str | None:
    for hour, minute in NEWSLETTER_SLOTS:
        start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start <= now < start + NEWSLETTER_CATCHUP:
            return f"newsletter:{start:%Y-%m-%d-%H%M}"
    return None


def run_due_jobs(reason: str) -> dict:
    """지금 해야 할 작업(뉴스 수집 · 뉴스레터)을 확인하고 밀린 것만 실행한다."""
    global _running
    if not _lock.acquire(blocking=False):
        return {"skipped": "이미 실행 중"}
    _running = True
    done: dict = {}
    try:
        now = datetime.now(KST)

        if _claim(_fetch_key(now)):
            from app.main import _fetch_news_job
            print(f"[예약 작업] 뉴스 수집 시작 ({reason})")
            _fetch_news_job()
            done["fetch"] = True

        slot = _due_newsletter_key(now)
        if slot and _claim(slot):
            from app.routers.admin_api import run_newsletter_job
            print(f"[예약 작업] 뉴스레터 발송 시작 {slot} ({reason})")
            done["newsletter"] = run_newsletter_job(public_base_url())
    except Exception as e:
        print(f"[예약 작업] 실패 ({reason}): {e}")
        done["error"] = str(e)
    finally:
        _running = False
        _lock.release()
    return done


def start_due_jobs(reason: str) -> bool:
    """밀린 작업을 백그라운드로 실행 (응답은 기다리지 않음)."""
    if _running:
        return False
    threading.Thread(target=run_due_jobs, args=(reason,), daemon=True).start()
    return True


@router.post("/fetch-news", status_code=202)
def run_fetch_news(
    x_cron_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
):
    """크론 진입점 — 뉴스 수집과 (발송 시각이면) 뉴스레터까지 한 번에 처리."""
    _check_secret(x_cron_secret, secret)
    started = start_due_jobs("cron")
    return {"started": started, "message": "예약 작업을 확인합니다." if started else "이미 실행 중입니다."}


@router.post("/newsletter", status_code=202)
def run_newsletter(
    x_cron_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
):
    """뉴스레터 시각이면 발송 (이미 보낸 회차는 다시 보내지 않음)."""
    _check_secret(x_cron_secret, secret)
    started = start_due_jobs("cron-newsletter")
    return {"started": started, "message": "예약 작업을 확인합니다." if started else "이미 실행 중입니다."}
