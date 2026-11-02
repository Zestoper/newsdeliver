"""기사 발행 시각 처리.

news.created_at 은 원래 'DB에 넣은 시각'이라서 수집이 밀렸다가 한 번에 들어오면
모든 기사가 같은 날짜로 찍혔다. 이제 원본 기사의 발행 시각을 created_at 에 넣는다.

- 네이버 뉴스 API: pubDate  (예: "Mon, 02 Nov 2026 20:15:00 +0900")
- RSS: published_parsed / updated_parsed  (feedparser가 UTC로 바꿔 줌)

저장은 INSERT 쪽 PUBLISHED_AT_SQL 로 한다.
시간대가 붙은 ISO 문자열을 DB 세션 시간대 기준 TIMESTAMP 로 바꿔서
기존 CURRENT_TIMESTAMP 로 들어간 행과 같은 기준을 유지한다.
발행 시각이 없거나 미래 시각이면 지금 시각을 쓴다.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

PUBLISHED_AT_SQL = (
    "LEAST(COALESCE(CAST(:published_at AS TIMESTAMPTZ), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)::timestamp"
)


def from_rfc822(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def from_struct_time(value) -> str | None:
    if not value:
        return None
    try:
        return datetime(*value[:6], tzinfo=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None
