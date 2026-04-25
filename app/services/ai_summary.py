import httpx
from sqlalchemy import text
from app.database import engine

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"

_PROMPT_TEMPLATE = (
    "뉴스를 2문장으로 요약해줘. 사실만, 마침표로 끝내줘.\n"
    "제목: {title}\n본문: {body}"
)


def _call_ollama(title: str, content: str) -> str:
    body = content.strip().replace("\n", " ")[:800]
    prompt = _PROMPT_TEMPLATE.format(title=title, body=body)
    try:
        res = httpx.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        res.raise_for_status()
        return res.json().get("response", "").strip()
    except Exception:
        return ""


def get_or_create_summary(news_id: int, title: str, content: str) -> str:
    """DB에 캐시된 요약이 있으면 반환, 없으면 생성 후 저장."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT ai_summary FROM news WHERE id = :id"),
            {"id": news_id},
        ).fetchone()

    if row and row.ai_summary:
        return row.ai_summary

    summary = _call_ollama(title, content)
    if summary:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE news SET ai_summary = :s WHERE id = :id"),
                {"s": summary, "id": news_id},
            )
            conn.commit()
    return summary


def summarize_articles(articles: list[dict]) -> list[dict]:
    """articles 리스트에 'ai_summary' 키를 추가해서 반환. DB 캐시 활용."""
    result = []
    for article in articles:
        # _load_subscriber_articles에서 SELECT n.*로 이미 로드된 값 우선 사용
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
