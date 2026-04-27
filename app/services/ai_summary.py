import time
import threading
import httpx
from sqlalchemy import text
from app.database import engine
from app.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

_groq_lock = threading.Lock()
_last_call_time = 0.0
_MIN_INTERVAL = 3.0  # 분당 최대 20회 (30회 한도 대비 여유)

_PROMPT_TEMPLATE = (
    "뉴스를 2문장으로 요약해줘. 사실만, 마침표로 끝내줘.\n"
    "제목: {title}\n본문: {body}"
)


def _call_groq(title: str, content: str) -> str:
    body = content.strip().replace("\n", " ")[:800]
    if not body:
        body = title
    prompt = _PROMPT_TEMPLATE.format(title=title, body=body)

    with _groq_lock:  # API 호출 전체를 직렬화 — 동시 호출 완전 차단
        global _last_call_time
        elapsed = time.time() - _last_call_time
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        _last_call_time = time.time()

        for attempt in range(5):
            try:
                res = httpx.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    json={
                        "model": GROQ_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 200,
                    },
                    timeout=15,
                )
                if res.status_code == 429:
                    wait = min(2 ** attempt, 30)
                    print(f"[AI요약] 429 (attempt {attempt+1}/5), {wait}s 대기")
                    time.sleep(wait)
                    continue
                res.raise_for_status()
                return res.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                print(f"[AI요약] 실패 (attempt {attempt+1}/5): {e} | {title[:30]}")
                if attempt < 4:
                    time.sleep(min(2 ** attempt, 30))

        print(f"[AI요약] 최종 실패: {title[:50]}")
        return ""


def get_or_create_summary(news_id: int, title: str, content: str) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT ai_summary FROM news WHERE id = :id"),
            {"id": news_id},
        ).fetchone()

    if row and row.ai_summary:
        return row.ai_summary

    summary = _call_groq(title, content)
    if summary:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE news SET ai_summary = :s WHERE id = :id"),
                {"s": summary, "id": news_id},
            )
            conn.commit()
    return summary


def summarize_articles(articles: list[dict]) -> list[dict]:
    result = []
    for article in articles:
        if article.get("ai_summary"):
            result.append(article)
            continue

        news_id = article.get("id")
        summary = get_or_create_summary(
            news_id=news_id,
            title=article.get("title", ""),
            content=article.get("content", ""),
        ) if news_id else ""
        result.append({**article, "ai_summary": summary})
    return result
