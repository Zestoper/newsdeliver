import html as _html
import httpx
import re
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text, bindparam
from app.database import engine
from app.config import settings

CLIENT_ID = settings.NAVER_CLIENT_ID
CLIENT_SECRET = settings.NAVER_CLIENT_SECRET

CATEGORY_KEYWORDS = {
    "정치": "정치 뉴스",
    "경제": "경제 뉴스",
    "IT": "IT 기술 뉴스",
    "문화": "문화 뉴스",
    "스포츠": "스포츠 뉴스",
    "예술": "예술 뉴스",
    "연예": "연예 뉴스",
    "국제": "국제 뉴스",
    "사회": "사회 뉴스",
}

_GARBAGE_MARKERS = [
    'window.__ht', 'pstatic.net',
    '"write_placeholder"', '"sort_favorite"', 'duplicate_caution',
]

_FOOTER_MARKERS = [
    # 기호류
    '※', '▶', '◆', '■', '☞', '☛',
    # 저작권
    'Copyright', 'copyright', 'ⓒ', '©', '저작권자', '&copy;',
    # 전재/재배포
    '무단 전재', '무단전재', '재배포 금지',
    # 제보
    '제보는', '제보하기', '여러분의 제보', '기사제보',
    # 관련/추천 기사 섹션 (한국어)
    '다른기사 보기', '다른 기사 보기', '관련기사', '관련 기사',
    '당신만 안 본 뉴스', '많이 본 뉴스', '인기 뉴스',
    '주요기사', '최신뉴스', '포토뉴스', '하단메뉴', '하단영역',
    '이용약관', '개인정보처리방침',
    # 영문 매체 관련기사·추천 섹션
    'More from the BBC', 'More from BBC',
    '\nRelated\n', '\nRelated topics\n', '\nRelated articles\n',
    'You may also like', 'Read more:', 'Also read:',
    'More stories', 'More news', 'Trending now',
    'Most read', 'Top stories', 'Latest news',
    # 영문 안전 고지 (BBC 등)
    'If you, or someone you know',
    'If you are affected by',
    'For help and support,',
    # 영문 저작권·면책
    'All rights reserved', 'Terms of Use', 'Privacy Policy',
    'Terms & Conditions',
    # Al Jazeera 고유 푸터
    'aj-logo', 'Code of Ethics',
    'EU/EEA Regulatory Notice',
    '\nAbout\n', 'AboutShow more',
    # 공통 영문 사이트 푸터
    'Follow us on', 'Subscribe to our newsletter',
    'Download our app', 'Get the app',
    'Sign up for', 'Newsletter sign',
    '\nShare\n', 'Click here to share',
    'share-nodes',
]

# 본문 중간에도 나타나지만 단독 줄이면 제거할 노이즈 패턴
_INLINE_NOISE_RE = re.compile(
    r'^\s*(Advertisement|Sponsored|Listen|ListenListen.*|Save|ShareSave'
    r'|facebookxwhatsapp.*|googleAdd.*|share-nodes.*'
    r'|aj-logo.*|ListenListen.*)\s*$',
    re.MULTILINE | re.IGNORECASE,
)

_SENTENCE_ENDS = ['다. ', '요. ', '다.', '요.', '다!', '다?', '. ']

# HTML 엔티티 → 일반 문자 매핑 (unescape 후 추가 정규화)
_CHAR_MAP = {
    '\xa0': ' ',       # &nbsp;
    '‘': "'",     # &lsquo; 왼쪽 홑따옴표
    '’': "'",     # &rsquo; 오른쪽 홑따옴표
    '“': '"',     # &ldquo; 왼쪽 겹따옴표
    '”': '"',     # &rdquo; 오른쪽 겹따옴표
    '…': '...',   # &hellip; 말줄임표
    '·': '·',     # &middot; 가운뎃점
    '—': '—',     # &mdash; 대시
    '–': '–',     # &ndash; 엔대시
    '©': '',           # 저작권 기호 제거
    'ⓒ': '',
}

def _normalize_chars(text: str) -> str:
    text = _html.unescape(text)
    for src, dst in _CHAR_MAP.items():
        text = text.replace(src, dst)
    return text

def _cut_at(text: str, idx: int) -> str:
    prefix = text[:idx]
    ends = [prefix.rfind(e) for e in _SENTENCE_ENDS]
    last = max(ends)
    return (prefix[:last + 2] if last >= 0 else prefix).strip()

def clean_article_text(text: str) -> str:
    # 1) 문자 정규화 (HTML 엔티티, 특수 따옴표, nbsp 등)
    text = _normalize_chars(text)

    # 2) 단독 줄 노이즈 제거 (Advertisement, aj-logo, Listen 버튼 등)
    text = _INLINE_NOISE_RE.sub('', text)

    # 3) 사진 출처 인라인 제거: (사진=XXX), [사진=XXX], ⓒXXX
    text = re.sub(r'[(\[]\s*사진\s*[=:][^\)\]]{1,30}[\)\]]', '', text)
    text = re.sub(r'ⓒ\s*\S+', '', text)

    # 4) 기자명·이메일 줄 제거 (단독 줄에 있는 경우)
    text = re.sub(r'\n[ \t]*\S{1,6}\s*기자[ \t]*\n', '\n', text)
    text = re.sub(r'\n[ \t]*[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}[ \t]*\n', '\n', text)

    # 5) JS/JSON 광고 스크립트 제거
    for marker in _GARBAGE_MARKERS:
        idx = text.find(marker)
        if idx == -1:
            continue
        w = text.rfind('window.', 0, idx + len(marker))
        cut = w if (w != -1 and idx - w < 300) else idx
        text = _cut_at(text, cut)
        break

    # 6) 푸터/저작권/관련기사 — 가장 앞에 나오는 마커 기준으로 자름
    earliest_idx = len(text)
    for marker in _FOOTER_MARKERS:
        idx = text.find(marker)
        if idx != -1 and idx < earliest_idx:
            earliest_idx = idx
    if earliest_idx < len(text):
        text = _cut_at(text, earliest_idx)

    # 7) 남은 window.xxx 제거 및 공백 정리
    text = re.sub(r'window\.[^\s가-힣]*\s*=\s*[^가-힣]*', '', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


_ID_SELECTORS = [
    'dic_area', 'articleBodyContents', 'articleBody', 'article-body', 'news_body',
    'article_body', 'news-content', 'article-content', 'news_content', 'content_body',
    'article_txt', 'news_txt', 'view_con', 'articleText', 'viewArticle',
    'article-view-content-div', 'article_view', 'news_view', 'view-article',
    'newsContent', 'news-article', 'article_area', 'read_body', 'rdcont',
    'content-article', 'postContent', 'news-story', 'articleWrap',
]

_CLASS_SELECTORS = [
    'article-body', 'article_body', 'articleBody', 'news-body', 'news_body',
    'article-content', 'article_content', 'news-content', 'view-content',
    'article-text', 'article_text', 'entry-content', 'post-content',
    'article_txt', 'news_txt', 'view_con', 'article_view', 'news_view',
    'content-body', 'article-wrap', 'news_article', 'article__body',
    'article-detail', 'news-detail', 'view_content', 'read-content',
    'article_content_wrap', 'article-area', 'main-article',
]

_SCRAPE_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ko-KR,ko;q=0.9',
}

def _parse_raw(raw: str) -> str:
    raw = re.sub(r'<(script|style)[^>]*>[\s\S]*?</(script|style)>', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
    raw = re.sub(r'</(p|div|li|h[1-6])>', '\n', raw, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', raw)
    text = _normalize_chars(text)          # 엔티티 디코딩 + 문자 정규화
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text).strip()
    return clean_article_text(text)


def _fetch_html(url, timeout=10):
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=_SCRAPE_HEADERS) as client:
        res = client.get(url)
        return res.text if res.status_code == 200 else None

def _content_from_html(html):
    # 1) id 속성으로 검색
    for sel in _ID_SELECTORS:
        for attr in [f'id="{sel}"', f"id='{sel}'"]:
            idx = html.find(attr)
            if idx == -1:
                continue
            tag_end = html.find('>', idx)
            if tag_end == -1:
                continue
            text = _parse_raw(html[tag_end + 1: tag_end + 200_000])
            if len(text) > 100:
                return text

    # 2) class 속성으로 검색
    for sel in _CLASS_SELECTORS:
        for attr in [f'class="{sel}"', f"class='{sel}'",
                     f'class="{sel} ', f"class='{sel} "]:
            idx = html.find(attr)
            if idx == -1:
                continue
            tag_end = html.find('>', idx)
            if tag_end == -1:
                continue
            text = _parse_raw(html[tag_end + 1: tag_end + 200_000])
            if len(text) > 100:
                return text

    # 3) <article> 태그 fallback
    for tag in ['<article', '<main']:
        idx = html.find(tag)
        if idx != -1:
            tag_end = html.find('>', idx)
            if tag_end != -1:
                text = _parse_raw(html[tag_end + 1: tag_end + 200_000])
                if len(text) > 100:
                    return text

    # 4) 최후 수단: 본문 <p> 태그를 모두 수집해서 이어붙이기
    paragraphs = re.findall(r'<p[^>]*>([\s\S]*?)</p>', html, re.IGNORECASE)
    collected = []
    for p in paragraphs:
        p_clean = re.sub(r'<[^>]+>', '', p)
        p_clean = re.sub(r'[ \t]+', ' ', p_clean).strip()
        if len(p_clean) > 30:
            collected.append(p_clean)
    if collected:
        text = clean_article_text('\n'.join(collected))
        if len(text) > 100:
            return text
    return None

def extract_full_content(url):
    try:
        html = _fetch_html(url)
        return _content_from_html(html) if html else None
    except Exception as e:
        print(f"본문 추출 중 오류 발생: {e}")
    return None

def _image_from_html(html):
    match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
    if not match:
        match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
    return match.group(1) if match else None

def scrape_article(url):
    """페이지를 한 번만 받아서 (본문, og:image) 를 함께 추출"""
    try:
        html = _fetch_html(url)
        if not html:
            return None, None
        return _content_from_html(html), _image_from_html(html)
    except Exception as e:
        print(f"본문 추출 중 오류 발생: {e}")
    return None, None

def extract_image_from_url(url):
    """bs4 없이 정규표현식(re)만 사용하여 og:image를 추출합니다."""
    try:
        html = _fetch_html(url, timeout=5)
        return _image_from_html(html) if html else None
    except Exception:
        return None

def extract_press_name(url: str) -> str:
    """URL에서 언론사명 추출"""
    domain_map = {
        "chosun": "조선일보", "joongang": "중앙일보", "donga": "동아일보",
        "hani": "한겨레", "khan": "경향신문", "ohmynews": "오마이뉴스",
        "yonhap": "연합뉴스", "yna": "연합뉴스", "newsis": "뉴시스",
        "news1": "뉴스1", "mt": "머니투데이", "mk": "매일경제",
        "hankyung": "한국경제", "sedaily": "서울경제", "etnews": "전자신문",
        "zdnet": "ZDNet", "itworld": "IT World", "bloter": "블로터",
        "newsworks": "뉴스웍스", "nocutnews": "노컷뉴스", "straightnews": "스트레이트뉴스",
    }
    for key, name in domain_map.items():
        if key in url:
            return name
    match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    if match:
        return match.group(1).split('.')[0]
    return url

def _clean_title(t: str) -> str:
    return t.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")


def fetch_and_save_news():
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }

    with engine.connect() as conn:
        categories = conn.execute(text("SELECT * FROM categories")).fetchall()
        category_map = {row.name: row.id for row in categories}

    # 1) 카테고리별 네이버 API 호출 — 병렬
    def _search(keyword):
        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=20&sort=date"
        try:
            res = httpx.get(url, headers=headers, timeout=10)
            return res.json().get("items", []) if res.status_code == 200 else []
        except Exception:
            return []

    targets = [(name, kw) for name, kw in CATEGORY_KEYWORDS.items() if category_map.get(name)]
    with ThreadPoolExecutor(max_workers=len(targets) or 1) as ex:
        results = list(ex.map(lambda t: _search(t[1]), targets))

    # 2) 이번 실행 내 중복 제목 제거
    items = []
    seen_titles: set[str] = set()
    for (category_name, _), api_items in zip(targets, results):
        for item in api_items:
            title = _clean_title(item["title"])
            link = item.get("originallink", "") or item.get("link", "")
            naver_link = item.get("link", "")
            # 컬럼 길이 초과 행이 있으면 일괄 INSERT 전체가 실패하므로 미리 제외
            if title in seen_titles or len(title) > 255 or len(link) > 500 or len(naver_link) > 500:
                continue
            seen_titles.add(title)
            items.append({
                "title": title,
                "description": _clean_title(item["description"]),
                "source": extract_press_name(item.get("originallink", ""))[:255],
                "link": link,
                "naver_link": naver_link,
                "category_id": category_map[category_name],
            })
    if not items:
        return 0

    # 3) DB 중복 체크 — 쿼리 한 번으로
    with engine.connect() as conn:
        existing = {
            r.title: r for r in conn.execute(
                text("SELECT id, title, LENGTH(COALESCE(content, '')) AS clen FROM news WHERE title IN :titles").bindparams(bindparam("titles", expanding=True)),
                {"titles": [it["title"] for it in items]},
            )
        }

    new_items = [it for it in items if it["title"] not in existing]
    refresh_items = [
        it for it in items
        if it["title"] in existing and existing[it["title"]].clen < 1000 and it["naver_link"]
    ]

    # 4) 본문 + 이미지 스크래핑 — 페이지 1회 다운로드, 병렬
    to_scrape = new_items + refresh_items
    with ThreadPoolExecutor(max_workers=10) as ex:
        scraped = list(ex.map(lambda it: scrape_article(it["naver_link"]) if it["naver_link"] else (None, None), to_scrape))

    inserts, updates = [], []
    for it, (content, image_url) in zip(to_scrape, scraped):
        if it["title"] in existing:
            if content and len(content) > existing[it["title"]].clen:
                updates.append({"content": content, "link": it["link"],
                                "naver_link": it["naver_link"], "id": existing[it["title"]].id})
        else:
            inserts.append({
                "title": it["title"],
                "content": content or it["description"],
                "source": it["source"],
                "image_url": image_url if image_url and len(image_url) <= 500 else None,
                "link": it["link"],
                "naver_link": it["naver_link"],
                "category_id": it["category_id"],
            })

    # 5) 일괄 저장 — 한 번의 트랜잭션
    with engine.connect() as conn:
        if inserts:
            conn.execute(
                text("""
                    INSERT INTO news (title, content, source, image_url, link, naver_link, status, category_id)
                    VALUES (:title, :content, :source, :image_url, :link, :naver_link, 'published', :category_id)
                    ON CONFLICT DO NOTHING
                """),
                inserts,
            )
        if updates:
            conn.execute(
                text("UPDATE news SET content = :content, link = :link, naver_link = :naver_link WHERE id = :id"),
                updates,
            )
        conn.commit()

    return len(inserts)
