import re
import httpx
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from app.database import engine

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}

# ══════════════════════════════════════════════════════════════════════
# RSS 피드 소스 (API 없이 직접 수집)
# pageSize: 피드에서 가져올 최대 기사 수
# ══════════════════════════════════════════════════════════════════════
RSS_SOURCES = [
    # ── The New York Times ──────────────────────────────────────────────
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",   "db_category": "IT",     "limit": 15},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",     "db_category": "경제",   "limit": 15},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",        "db_category": "국제",   "limit": 15},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",     "db_category": "정치",   "limit": 10},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml",         "db_category": "예술",   "limit": 10},
    # ── The Wall Street Journal ─────────────────────────────────────────
    {"url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",                   "db_category": "국제",   "limit": 15},
    {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                 "db_category": "경제",   "limit": 15},
    {"url": "https://feeds.a.dj.com/rss/RSSWSJD.xml",                        "db_category": "IT",     "limit": 15},
    # ── Los Angeles Times ───────────────────────────────────────────────
    {"url": "https://www.latimes.com/world-nation/rss2.0.xml",                "db_category": "국제",   "limit": 15},
    {"url": "https://www.latimes.com/business/rss2.0.xml",                    "db_category": "경제",   "limit": 15},
    {"url": "https://www.latimes.com/entertainment-arts/rss2.0.xml",          "db_category": "연예",   "limit": 15},
    {"url": "https://www.latimes.com/sports/rss2.0.xml",                      "db_category": "스포츠", "limit": 15},
    # ── BBC News ────────────────────────────────────────────────────────
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",                    "db_category": "국제",   "limit": 20},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",                 "db_category": "경제",   "limit": 20},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",               "db_category": "IT",     "limit": 20},
    {"url": "https://feeds.bbci.co.uk/news/politics/rss.xml",                 "db_category": "정치",   "limit": 15},
    {"url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",   "db_category": "연예",   "limit": 15},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",  "db_category": "사회",   "limit": 15},
    {"url": "https://feeds.bbci.co.uk/news/health/rss.xml",                   "db_category": "사회",   "limit": 15},
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml",                         "db_category": "스포츠", "limit": 20},
    # ── The Guardian ────────────────────────────────────────────────────
    {"url": "https://www.theguardian.com/world/rss",                          "db_category": "국제",   "limit": 20},
    {"url": "https://www.theguardian.com/business/rss",                       "db_category": "경제",   "limit": 15},
    {"url": "https://www.theguardian.com/sport/rss",                          "db_category": "스포츠", "limit": 15},
    {"url": "https://www.theguardian.com/technology/rss",                     "db_category": "IT",     "limit": 15},
    {"url": "https://www.theguardian.com/culture/rss",                        "db_category": "문화",   "limit": 10},
    {"url": "https://www.theguardian.com/music/rss",                          "db_category": "예술",   "limit": 10},
    {"url": "https://www.theguardian.com/politics/rss",                       "db_category": "정치",   "limit": 10},
    # ── Daily Telegraph ─────────────────────────────────────────────────
    {"url": "https://www.telegraph.co.uk/rss.xml",                            "db_category": "국제",   "limit": 15},
    # ── NPR News ────────────────────────────────────────────────────────
    {"url": "https://feeds.npr.org/1004/rss.xml",                             "db_category": "국제",   "limit": 20},
    {"url": "https://feeds.npr.org/1006/rss.xml",                             "db_category": "경제",   "limit": 15},
    {"url": "https://feeds.npr.org/1019/rss.xml",                             "db_category": "IT",     "limit": 15},
    # ── Sky News (The Times 대체) ────────────────────────────────────────
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml",                  "db_category": "국제",   "limit": 20},
    {"url": "https://feeds.skynews.com/feeds/rss/business.xml",               "db_category": "경제",   "limit": 15},
    {"url": "https://feeds.skynews.com/feeds/rss/technology.xml",             "db_category": "IT",     "limit": 15},
    {"url": "https://feeds.skynews.com/feeds/rss/politics.xml",               "db_category": "정치",   "limit": 10},
    # ── IT (기존) ────────────────────────────────────────────────────────
    {"url": "https://techcrunch.com/feed/",                                    "db_category": "IT",     "limit": 20},
    {"url": "https://www.theverge.com/rss/index.xml",                         "db_category": "IT",     "limit": 20},
    {"url": "https://feeds.arstechnica.com/arstechnica/index",                "db_category": "IT",     "limit": 15},
    # ── 경제 (기존) ──────────────────────────────────────────────────────
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/",          "db_category": "경제",   "limit": 20},
    {"url": "https://www.investing.com/rss/news.rss",                         "db_category": "경제",   "limit": 15},
    # ── 스포츠 (기존) ────────────────────────────────────────────────────
    {"url": "https://www.espn.com/espn/rss/news",                             "db_category": "스포츠", "limit": 25},
    # ── 연예 (기존) ──────────────────────────────────────────────────────
    {"url": "https://variety.com/feed/",                                       "db_category": "연예",   "limit": 20},
    {"url": "https://www.hollywoodreporter.com/t/entertainment/feed/",        "db_category": "연예",   "limit": 15},
    # ── 정치 (기존) ──────────────────────────────────────────────────────
    {"url": "https://rss.politico.com/politics-news.xml",                     "db_category": "정치",   "limit": 20},
    {"url": "https://thehill.com/homenews/feed/",                             "db_category": "정치",   "limit": 15},
    # ── 예술 (기존) ──────────────────────────────────────────────────────
    {"url": "https://www.nme.com/feed",                                        "db_category": "예술",   "limit": 15},
    {"url": "https://consequenceofsound.net/feed/",                           "db_category": "예술",   "limit": 15},
    # ── 사회·과학 (기존) ─────────────────────────────────────────────────
    {"url": "https://www.sciencedaily.com/rss/all.xml",                       "db_category": "사회",   "limit": 25},
    {"url": "https://www.livescience.com/feeds/all",                          "db_category": "사회",   "limit": 20},
    # ── 국제 (기존) ──────────────────────────────────────────────────────
    {"url": "https://www.aljazeera.com/xml/rss/all.xml",                     "db_category": "국제",   "limit": 25},
    # ── 문화 (기존) ──────────────────────────────────────────────────────
    {"url": "https://www.smithsonianmag.com/rss/latest_articles/",           "db_category": "문화",   "limit": 15},
]

# ══════════════════════════════════════════════════════════════════════
# 카테고리별 필수 키워드
# ══════════════════════════════════════════════════════════════════════
REQUIRED: dict[str, list[str]] = {
    "IT": [
        "tech", "software", "hardware", "ai", "artificial intelligence",
        "machine learning", "startup", "app", "cloud", "cybersecurity",
        "cyber", "data", "algorithm", "robot", "semiconductor", "silicon",
        "digital", "code", "programming", "chip", "smartphone", "internet",
        "computer", "gpu", "server", "developer", "open source", "gadget",
        "quantum", "blockchain", "5g", "electric vehicle", "self-driving",
        "augmented reality", "virtual reality", "vr", "ar",
    ],
    "경제": [
        "economy", "economic", "market", "stock", "finance", "financial",
        "investment", "gdp", "inflation", "trade", "dollar", "earnings",
        "revenue", "profit", "bank", "fund", "bond", "commodity",
        "recession", "fiscal", "monetary", "interest rate", "crypto",
        "bitcoin", "tariff", "export", "import", "debt", "budget",
        "tax", "ipo", "acquisition", "merger", "wall street",
    ],
    "스포츠": [
        "sport", "game", "match", "tournament", "player", "team",
        "season", "championship", "league", "coach", "score", "win",
        "loss", "athlete", "olympic", "cup", "soccer", "football",
        "basketball", "baseball", "tennis", "golf", "nba", "nfl",
        "mlb", "nhl", "fifa", "formula", "racing", "swimming", "gym",
    ],
    "연예": [
        "actor", "actress", "singer", "film", "movie", "award",
        "grammy", "oscar", "emmy", "album", "concert", "netflix",
        "hulu", "disney", "box office", "premiere", "trailer", "sequel",
        "celebrity", "hollywood", "streaming", "episode", "season finale",
        "music video", "chart", "single", "debut", "biopic",
    ],
    "문화": [
        "culture", "travel", "food", "museum", "exhibition", "festival",
        "nature", "wildlife", "history", "heritage", "cuisine", "design",
        "photography", "geography", "expedition", "discovery", "tribe",
        "civilization", "ancient", "tradition", "religion", "ritual",
        "national park", "ocean", "rainforest", "species", "planet",
    ],
    "예술": [
        "music", "album", "song", "band", "artist", "concert", "tour",
        "painting", "gallery", "sculpture", "theatre", "opera", "jazz",
        "rock", "hip-hop", "classical", "composer", "vinyl", "art",
        "performance", "studio", "record label", "debut album",
        "music festival", "choreography", "dance", "film score",
    ],
    "사회": [
        "health", "science", "research", "study", "medicine", "disease",
        "vaccine", "climate", "environment", "space", "nasa", "biology",
        "chemistry", "physics", "mental health", "hospital", "drug",
        "experiment", "discovery", "species", "fossil", "psychology",
        "neuroscience", "gene", "dna", "cancer", "surgery", "epidemic",
        "astronomy", "planet", "ocean", "ecology", "evolution",
    ],
    "국제": [
        "world", "global", "international", "war", "conflict", "peace",
        "crisis", "summit", "foreign", "refugee", "humanitarian",
        "united nations", "nato", "eu", "european", "africa", "asia",
        "middle east", "south america", "migration", "border",
        "bilateral", "treaty", "sanction", "diplomat", "geopolit",
        "u.k.", "britain", "british", "france", "germany", "japan",
        "canada", "australia", "india", "korea", "israel", "iran",
        "russia", "ukraine", "china", "lawmakers", "parliament",
        "royal", "king", "queen", "prime minister", "chancellor",
    ],
    "정치": [
        "government", "president", "senate", "u.s. congress", "election",
        "vote", "policy", "court", "white house", "minister",
        "parliament", "democrat", "republican", "political",
        "legislation", "federal", "campaign", "administration",
        "supreme court", "governor", "ballot", "primary",
    ],
}

POLITICS_BLOCK_TERMS = [
    "trump", "donald trump", "biden", "kamala", "harris", "obama",
    "desantis", "pelosi", "mcconnell", "bernie", "aoc", "ocasio-cortez",
    "u.s. congress", "senate", "white house", "oval office",
    "manifesto", "impeach", "indictment", "arraignment",
    "maga", "gop ", " gop,",
    "shooting rampage", "mass shooting", "gunman",
    "whcd", "correspondents dinner",
]

_REROUTE_ECO = [
    "tariff", "trade", "economy", "economic", "market", "stock",
    "tax", "budget", "fiscal", "gdp", "inflation", "dollar",
    "import", "export", "deal", "revenue", "deficit",
]
_REROUTE_INTL = [
    "ukraine", "russia", "china", "iran", "north korea",
    "nato", "europe", "european", "asia", "middle east", "africa",
    "foreign", "international", "summit", "diplomatic", "war", "military",
    "treaty", "bilateral", "refugee", "geopolit",
    "u.k.", "britain", "british", "france", "germany", "japan",
    "canada", "australia", "india", "israel",
    "lawmakers", "parliament", "king charles", "prime minister",
]


def _kw_match(keyword: str, text: str) -> bool:
    if ' ' in keyword or '-' in keyword or '.' in keyword:
        return keyword in text
    return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))


def _classify(title: str, description: str, hint_category: str) -> str | None:
    title_lower = title.lower()
    desc_lower = (description or "").lower()
    text_lower = title_lower + " " + desc_lower

    if any(_kw_match(t, text_lower) for t in POLITICS_BLOCK_TERMS):
        if any(_kw_match(k, text_lower) for k in _REROUTE_ECO):
            return "경제"
        if any(_kw_match(k, text_lower) for k in _REROUTE_INTL):
            return "국제"
        return "정치"

    scores: dict[str, int] = {
        cat: sum(2 for kw in kws if _kw_match(kw, title_lower))
            + sum(1 for kw in kws if _kw_match(kw, desc_lower))
        for cat, kws in REQUIRED.items()
    }

    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]
    hint_score = scores.get(hint_category, 0)

    if best_score == 0:
        return None

    title_max = max(
        sum(1 for kw in kws if _kw_match(kw, title_lower))
        for kws in REQUIRED.values()
    )
    if title_max == 0 and best_score <= 1:
        return None

    if best_score > hint_score:
        return best_cat
    return hint_category


def _entry_to_article(entry: dict, feed_title: str) -> dict:
    """feedparser 엔트리를 내부 article 딕셔너리로 변환."""
    title = entry.get("title", "").strip()
    summary = entry.get("summary", "") or ""
    # HTML 태그 제거
    summary = re.sub(r"<[^>]+>", " ", summary).strip()

    link = entry.get("link", "").strip()

    # 이미지: media_thumbnail > media_content > enclosures 순으로 탐색
    image_url = ""
    for thumb in entry.get("media_thumbnail", []):
        image_url = thumb.get("url", "")
        if image_url:
            break
    if not image_url:
        for media in entry.get("media_content", []):
            if media.get("medium") == "image" or media.get("type", "").startswith("image"):
                image_url = media.get("url", "")
                if image_url:
                    break
    if not image_url:
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("image"):
                image_url = enc.get("url", "")
                break

    # 본문: content > summary
    content_text = ""
    for c in entry.get("content", []):
        content_text = re.sub(r"<[^>]+>", " ", c.get("value", "")).strip()
        if content_text:
            break
    if not content_text:
        content_text = summary

    return {
        "title": title,
        "description": summary,
        "url": link,
        "urlToImage": image_url,
        "content": content_text,
        "source": {"name": feed_title},
    }


def _fetch_rss(url: str, limit: int) -> list[dict]:
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=6, follow_redirects=True)
        if r.status_code != 200:
            print(f"[해외뉴스] RSS 요청 실패 ({r.status_code}): {url[:70]}")
            return []
        feed = feedparser.parse(r.text)
        if not feed.entries:
            print(f"[해외뉴스] RSS 기사 없음: {url[:70]}")
            return []
        feed_title = feed.feed.get("title", "") if feed.feed else ""
        return [_entry_to_article(e, feed_title) for e in feed.entries[:limit]]
    except Exception as e:
        print(f"[해외뉴스] RSS 오류 ({url[:70]}): {e}")
        return []


def _save(article: dict, category_id: int, category_name: str, seen: set,
          cat_map: dict | None = None) -> bool:
    title = (article.get("title") or "").strip()
    if not title or title == "[Removed]" or title in seen:
        return False

    description = (article.get("description") or "").strip()

    final_cat = _classify(title, description, category_name)
    if final_cat is None:
        return False

    if final_cat != category_name:
        if cat_map is None:
            return False
        new_id = cat_map.get(final_cat)
        if not new_id:
            return False
        category_id, category_name = new_id, final_cat

    seen.add(title)

    link        = (article.get("url") or "").strip()
    source_name = (article.get("source") or {}).get("name") or ""
    image_url   = article.get("urlToImage") or ""
    content_api = (article.get("content") or "").strip()

    with engine.connect() as conn:
        if conn.execute(text("SELECT id FROM news WHERE title = :t"), {"t": title}).fetchone():
            return False

    full_content = content_api if len(content_api) > len(description) else description
    if not full_content:
        full_content = title

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO news
                    (title, content, source, image_url, link, naver_link,
                     status, category_id, is_global)
                VALUES
                    (:title, :content, :source, :image_url, :link, '',
                     'published', :category_id, 1)
                ON CONFLICT DO NOTHING
            """),
            {
                "title": title, "content": full_content,
                "source": source_name, "image_url": image_url,
                "link": link, "category_id": category_id,
            }
        )
        conn.commit()
    return True


def fetch_and_save_global_news() -> int:
    with engine.connect() as conn:
        cat_map = {
            r.name: r.id
            for r in conn.execute(text("SELECT id, name FROM categories")).fetchall()
        }

    # RSS 피드 병렬 수집 (최대 12개 동시, 전체 타임아웃 45초)
    fetched: list[tuple[list[dict], str]] = []
    executor = ThreadPoolExecutor(max_workers=12)
    future_map = {
        executor.submit(_fetch_rss, src["url"], src["limit"]): src["db_category"]
        for src in RSS_SOURCES
    }
    try:
        for future in as_completed(future_map, timeout=45):
            cat_name = future_map[future]
            try:
                articles = future.result()
            except Exception:
                articles = []
            if articles:
                fetched.append((articles, cat_name))
    except Exception:
        pass
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    saved = 0
    seen: set[str] = set()
    for articles, cat_name in fetched:
        cat_id = cat_map.get(cat_name)
        if not cat_id:
            continue
        for article in articles:
            if _save(article, cat_id, cat_name, seen, cat_map):
                saved += 1

    print(f"[해외뉴스] 수집 완료: {saved}건")
    return saved
