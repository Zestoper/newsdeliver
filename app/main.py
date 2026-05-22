from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.database import engine
from app.config import settings
from app.routers.pages import router as pages_router
from app.routers.users import router as users_router
from app.routers.news import router as news_router
from app.routers.press import router as press_router
from app.routers.admin_api import router as admin_api_router
from app.routers.oauth import router as oauth_router
from app.routers.chat import router as chat_router

BASE_DIR = Path(__file__).resolve().parent

_POLITICS_TERMS = [
    "trump", "donald trump", "maga", "biden", "kamala", "harris",
    "obama", "desantis", "ocasio-cortez", "pelosi", "mcconnell",
    "u.s. congress", "senate", "white house", "manifesto", "impeach",
    "indictment", "arraignment", "whcd", "correspondents dinner",
    "mass shooting", "shooting rampage", "gunman",
]

def _reclassify_politics() -> int:
    from sqlalchemy import text as _text
    from app.services.global_news import _REROUTE_ECO, _REROUTE_INTL, _kw_match
    conditions = " OR ".join(
        f"LOWER(n.title) LIKE :t{i} OR LOWER(n.content) LIKE :t{i}"
        for i in range(len(_POLITICS_TERMS))
    )
    params = {f"t{i}": f"%{t}%" for i, t in enumerate(_POLITICS_TERMS)}
    with engine.connect() as conn:
        cat_map = {
            r.name: r.id
            for r in conn.execute(_text("SELECT id, name FROM categories")).fetchall()
        }
        rows = conn.execute(_text(f"""
            SELECT n.id, n.title, n.content FROM news n
            JOIN categories c ON n.category_id = c.id
            WHERE c.name IN ('문화', '예술', '연예', 'IT', '스포츠', '사회')
              AND ({conditions})
        """), params).fetchall()
        reclassified = 0
        for row in rows:
            text_lower = ((row.title or "") + " " + (row.content or "")[:500]).lower()
            if any(_kw_match(k, text_lower) for k in _REROUTE_ECO):
                new_cat = "경제"
            elif any(_kw_match(k, text_lower) for k in _REROUTE_INTL):
                new_cat = "국제"
            else:
                new_cat = "정치"
            new_id = cat_map.get(new_cat)
            if new_id:
                conn.execute(
                    _text("UPDATE news SET category_id = :cid WHERE id = :id"),
                    {"cid": new_id, "id": row.id},
                )
                reclassified += 1
        conn.commit()
    return reclassified


try:
    with engine.connect() as conn:
        print("✅ DB 연결 성공!")
        from sqlalchemy import text
        migrations = [
            ("ALTER TABLE news ADD COLUMN IF NOT EXISTS link VARCHAR(500)", "news.link"),
            ("ALTER TABLE news ADD COLUMN IF NOT EXISTS is_global SMALLINT DEFAULT 0", "news.is_global"),
            ("ALTER TABLE news ADD COLUMN IF NOT EXISTS naver_link VARCHAR(500)", "news.naver_link"),
            ("ALTER TABLE news ADD COLUMN IF NOT EXISTS view_count INT DEFAULT 0", "news.view_count"),
            ("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS is_verified SMALLINT DEFAULT 0", "subscriptions.is_verified"),
            ("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS verify_token VARCHAR(100)", "subscriptions.verify_token"),
            ("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS unique_email", "subscriptions.unique_email 제약 제거"),
            ("ALTER TABLE news_comments ADD COLUMN IF NOT EXISTS parent_id INT DEFAULT NULL", "news_comments.parent_id"),
            ("ALTER TABLE news_users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "news_users.created_at"),
            ("ALTER TABLE news ADD COLUMN IF NOT EXISTS ai_summary TEXT NULL", "news.ai_summary"),
            ("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(10) DEFAULT 'text'", "chat_messages.message_type"),
            ("ALTER TABLE news_users ADD COLUMN IF NOT EXISTS press_approved SMALLINT DEFAULT 0", "news_users.press_approved"),
            ("ALTER TABLE news_users ADD COLUMN IF NOT EXISTS press_notified SMALLINT DEFAULT 0", "news_users.press_notified"),
            ("ALTER TABLE category_subscriptions ADD COLUMN IF NOT EXISTS is_global SMALLINT DEFAULT 0", "category_subscriptions.is_global"),
            ("ALTER TABLE category_subscriptions DROP CONSTRAINT IF EXISTS unique_cat_sub", "category_subscriptions.unique_cat_sub 제거"),
            ("ALTER TABLE category_subscriptions ADD CONSTRAINT unique_cat_sub_global UNIQUE (user_id, category_id, is_global)", "category_subscriptions.unique_cat_sub_global"),
            ("ALTER TABLE chat_rooms ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT '일반문의'", "chat_rooms.category"),
            ("ALTER TABLE chat_rooms DROP CONSTRAINT IF EXISTS unique_user", "chat_rooms.drop_unique_user"),
            ("ALTER TABLE chat_rooms ADD CONSTRAINT unique_user_category UNIQUE (user_id, category)", "chat_rooms.unique_user_category"),
        ]
        # reports 테이블 생성
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    news_id INT NOT NULL,
                    reporter_id VARCHAR(50) NOT NULL,
                    reporter_name VARCHAR(100) NOT NULL,
                    reason VARCHAR(500) DEFAULT '',
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    news_id INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_bookmark UNIQUE (user_id, news_id)
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
                    id SERIAL PRIMARY KEY,
                    comment_id INT NOT NULL,
                    user_id VARCHAR(50) NOT NULL,
                    CONSTRAINT unique_comment_like UNIQUE (comment_id, user_id)
                )
            """))
            conn.commit()
            print("✅ comment_likes 테이블")
        except Exception:
            pass
        # news.title 중복 방지 UNIQUE 인덱스
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS unique_title ON news (title)"))
            conn.commit()
            print("✅ news.title unique index")
        except Exception:
            pass

        # 소셜 로그인용 컬럼 추가 및 pw NULL 허용
        oauth_migrations = [
            ("ALTER TABLE news_users ALTER COLUMN pw DROP NOT NULL", "news_users.pw nullable"),
            ("ALTER TABLE news_users ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(20) NULL", "news_users.oauth_provider"),
            ("ALTER TABLE news_users ADD COLUMN IF NOT EXISTS oauth_id VARCHAR(100) NULL", "news_users.oauth_id"),
            ("ALTER TABLE news_users ADD CONSTRAINT oauth_unique UNIQUE (oauth_provider, oauth_id)", "news_users.oauth_unique"),
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
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    user_name VARCHAR(100),
                    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_user UNIQUE (user_id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    room_id INT NOT NULL,
                    sender VARCHAR(10) NOT NULL,
                    message TEXT NOT NULL,
                    is_read SMALLINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    news_id INT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_sent UNIQUE (email, news_id)
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
                conn.execute(text("INSERT INTO categories (name) VALUES (:name) ON CONFLICT DO NOTHING"), {"name": cat})
                conn.commit()
                print(f"✅ 카테고리 추가: {cat}")
            except Exception:
                pass

        # 해외뉴스 카테고리 추가
        global_cats = ["해외IT", "해외경제", "해외국제", "해외문화",
                       "해외사회", "해외스포츠", "해외연예", "해외예술", "해외정치"]
        for cat in global_cats:
            try:
                conn.execute(text("INSERT INTO categories (name) VALUES (:name) ON CONFLICT DO NOTHING"), {"name": cat})
                conn.commit()
                print(f"✅ 카테고리 추가: {cat}")
            except Exception:
                pass

        # 기존 해외 기사: 해외XXX 카테고리 → 국내 카테고리로 이동 + is_global = 1 표시
        remap = {
            '해외IT': 'IT', '해외경제': '경제', '해외국제': '국제',
            '해외문화': '문화', '해외사회': '사회', '해외스포츠': '스포츠',
            '해외연예': '연예', '해외예술': '예술', '해외정치': '정치',
            '해외뉴스': '국제', '해외건강': '사회', '해외과학': '사회',
        }
        try:
            cat_rows = conn.execute(text("SELECT id, name FROM categories")).fetchall()
            cat_map = {r.name: r.id for r in cat_rows}
            total_remapped = 0
            for old_name, new_name in remap.items():
                old_id = cat_map.get(old_name)
                new_id = cat_map.get(new_name)
                if not old_id or not new_id:
                    continue
                r = conn.execute(text(
                    "UPDATE news SET category_id = :new_id, is_global = 1 WHERE category_id = :old_id"
                ), {"new_id": new_id, "old_id": old_id})
                conn.commit()
                total_remapped += r.rowcount
            if total_remapped:
                print(f"✅ 해외뉴스 카테고리 재분류: {total_remapped}건")
        except Exception as e:
            print(f"[해외뉴스 재분류] {e}")

        # naver_link 가 있는 기사 → 무조건 국내 (is_global = 0)
        try:
            r = conn.execute(text(
                "UPDATE news SET is_global = 0 WHERE naver_link IS NOT NULL AND naver_link != ''"
            ))
            conn.commit()
            if r.rowcount:
                print(f"✅ 국내뉴스 is_global 보정: {r.rowcount}건")
        except Exception as e:
            print(f"[is_global 국내 보정] {e}")

        # 문화·예술 카테고리 중 naver_link 있는 기사는 국내로 보정
        try:
            r = conn.execute(text("""
                UPDATE news n
                JOIN categories c ON n.category_id = c.id
                SET n.is_global = 0
                WHERE c.name IN ('문화', '예술')
                  AND n.naver_link IS NOT NULL AND n.naver_link != ''
            """))
            conn.commit()
            if r.rowcount:
                print(f"✅ 문화·예술 국내 보정: {r.rowcount}건")
        except Exception as e:
            print(f"[문화·예술 보정] {e}")

        # 해외뉴스 재분류 정리 — 카테고리 개선 후 1회만 실행
        try:
            already = conn.execute(text(
                "SELECT COUNT(*) FROM newsletter_sent WHERE email = '__global_purge_v9__' AND news_id = 0"
            )).scalar()
            if not already:
                conn.execute(text(
                    "INSERT INTO newsletter_sent (email, news_id) VALUES ('__global_purge_v9__', 0)"
                ))
                r = conn.execute(text("DELETE FROM news WHERE is_global = 1"))
                conn.commit()
                print(f"✅ 해외뉴스 전체 삭제: {r.rowcount}건 → 점수 기반 재분류 후 재수집 예정")
        except Exception as e:
            print(f"[해외뉴스 정리] {e}")

        # 잘못 분류된 정치 기사를 올바른 카테고리로 재분류
        try:
            count = _reclassify_politics()
            if count:
                print(f"✅ 정치 기사 재분류: {count}건")
        except Exception as e:
            print(f"[정치 기사 재분류] {e}")

except Exception as e:
    print(f"❌ DB 연결 실패: {e}")

KST = pytz.timezone("Asia/Seoul")


def _newsletter_job():
    from app.routers.admin_api import run_newsletter_job
    run_newsletter_job(base_url=settings.SERVER_BASE_URL)

def _fetch_news_job():
    from app.services.naver_news import fetch_and_save_news
    from app.services.global_news import fetch_and_save_global_news
    from sqlalchemy import text as _text
    try:
        count = fetch_and_save_news()
        print(f"[뉴스 자동수집] 국내 {count}개 저장")
    except Exception as e:
        print(f"[뉴스 자동수집] 국내 실패: {e}")
    try:
        global_count = fetch_and_save_global_news()
        print(f"[뉴스 자동수집] 해외 {global_count}개 저장")
    except Exception as e:
        print(f"[뉴스 자동수집] 해외 실패: {e}")

    # 잘못 분류된 정치 기사를 올바른 카테고리로 재분류 (수집 주기마다 실행)
    try:
        count = _reclassify_politics()
        if count:
            print(f"[정치 기사 재분류] {count}건 이동")
    except Exception as e:
        print(f"[정치 기사 재분류] {e}")


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