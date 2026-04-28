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

_PROMPT_GLOBAL = (
    "You must respond with EXACTLY this format and nothing else:\n"
    "EN::: [3 sentences in English summarizing the article]\n"
    "KO::: [3 sentences in Korean summarizing the article]\n\n"
    "Do NOT add any other text, labels, or explanation.\n\n"
    "Title: {title}\nBody: {body}"
)


def _call_groq(title: str, content: str, is_global: bool = False) -> str:
    body = content.strip().replace("\n", " ")[:800]
    if not body:
        body = title
    template = _PROMPT_GLOBAL if is_global else _PROMPT_TEMPLATE
    prompt = template.format(title=title, body=body)

    with _groq_lock:  # API 호출 전체를 직렬화 — 동시 호출 완전 차단
        global _last_call_time

        for attempt in range(5):
            elapsed = time.time() - _last_call_time
            if elapsed < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - elapsed)
            _last_call_time = time.time()

            try:
                res = httpx.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    json={
                        "model": GROQ_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 400 if is_global else 200,
                    },
                    timeout=15,
                )
                if res.status_code == 429:
                    wait = min(2 ** attempt, 30)
                    print(f"[AI요약] 429 (attempt {attempt+1}/5), {wait}s 대기")
                    time.sleep(wait)
                    continue
                res.raise_for_status()
                result = res.json()["choices"][0]["message"]["content"].strip()

                # 해외뉴스: EN:::, KO::: 둘 다 있어야 유효
                if is_global and ("EN:::" not in result or "KO:::" not in result):
                    print(f"[AI요약] 형식 불일치, 재시도 (attempt {attempt+1}/5): {title[:40]}")
                    continue

                return result
            except Exception as e:
                print(f"[AI요약] 실패 (attempt {attempt+1}/5): {e} | {title[:30]}")
                if attempt < 4:
                    time.sleep(min(2 ** attempt, 30))

        print(f"[AI요약] 최종 실패: {title[:50]}")
        return ""


def get_or_create_summary(news_id: int, title: str, content: str, is_global: bool = False) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT ai_summary FROM news WHERE id = :id"),
            {"id": news_id},
        ).fetchone()

    if row and row.ai_summary:
        return row.ai_summary

    summary = _call_groq(title, content, is_global=is_global)
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
        is_global = bool(article.get("is_global", 0))
        summary = get_or_create_summary(
            news_id=news_id,
            title=article.get("title", ""),
            content=article.get("content", ""),
            is_global=is_global,
        ) if news_id else ""
        result.append({**article, "ai_summary": summary})
    return result
