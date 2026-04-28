import html as _html
import httpx
import re
from sqlalchemy import text
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
    # 관련/추천 기사 섹션
    '다른기사 보기', '다른 기사 보기', '관련기사', '관련 기사',
    '당신만 안 본 뉴스', '많이 본 뉴스', '인기 뉴스',
    '주요기사', '최신뉴스', '포토뉴스', '하단메뉴', '하단영역',
    '이용약관', '개인정보처리방침',
]

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

    # 2) 사진 출처 인라인 제거: (사진=XXX), [사진=XXX], ⓒXXX
    text = re.sub(r'[(\[]\s*사진\s*[=:][^\)\]]{1,30}[\)\]]', '', text)
    text = re.sub(r'ⓒ\s*\S+', '', text)

    # 3) 기자명·이메일 줄 제거 (단독 줄에 있는 경우)
    text = re.sub(r'\n[ \t]*\S{1,6}\s*기자[ \t]*\n', '\n', text)
    text = re.sub(r'\n[ \t]*[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}[ \t]*\n', '\n', text)

    # 4) JS/JSON 광고 스크립트 제거
    for marker in _GARBAGE_MARKERS:
        idx = text.find(marker)
        if idx == -1:
            continue
        w = text.rfind('window.', 0, idx + len(marker))
        cut = w if (w != -1 and idx - w < 300) else idx
        text = _cut_at(text, cut)
        break

    # 5) 푸터/저작권/관련기사 — 가장 앞에 나오는 마커 기준으로 자름
    earliest_idx = len(text)
    for marker in _FOOTER_MARKERS:
        idx = text.find(marker)
        if idx != -1 and idx < earliest_idx:
            earliest_idx = idx
    if earliest_idx < len(text):
        text = _cut_at(text, earliest_idx)

    # 6) 남은 window.xxx 제거 및 공백 정리
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


def extract_full_content(url):
    try:
        with httpx.Client(timeout=10, follow_redirects=True, headers=_SCRAPE_HEADERS) as client:
            res = client.get(url)
            if res.status_code != 200:
                return None

            html = res.text

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

    except Exception as e:
        print(f"본문 추출 중 오류 발생: {e}")
    return None

def extract_image_from_url(url):
    """
    bs4 없이 정규표현식(re)만 사용하여 og:image를 추출합니다.
    """
    try:
        with httpx.Client(timeout=5, follow_redirects=True) as client:
            res = client.get(url)
            if res.status_code != 200:
                return None
            
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', res.text)
            if not match:
                match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', res.text)
            
            if match:
                return match.group(1)
    except Exception:
        return None
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

def fetch_and_save_news():
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }

    with engine.connect() as conn:
        categories = conn.execute(text("SELECT * FROM categories")).fetchall()
        category_map = {row.name: row.id for row in categories}

    total_saved = 0
    seen_titles: set[str] = set()  # 이번 실행에서 처리한 제목 추적 (중복 방지)

    for category_name, keyword in CATEGORY_KEYWORDS.items():
        category_id = category_map.get(category_name)
        if not category_id:
            continue

        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=20&sort=date"

        with httpx.Client() as client:
            res = client.get(url, headers=headers)
            if res.status_code != 200:
                continue
            data = res.json()

        for item in data.get("items", []):
            # 1. 기본 정보 정제
            title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
            source = extract_press_name(item.get("originallink", ""))
            link = item.get("originallink", "") or item.get("link", "")
            naver_link = item.get("link", "")

            # 2. 이번 실행 내 중복 제목 건너뜀
            if title in seen_titles:
                continue
            seen_titles.add(title)

            # 3. DB 중복 체크 — 기존 기사의 본문이 짧으면 업데이트
            with engine.connect() as conn:
                existing = conn.execute(
                    text("SELECT id, content FROM news WHERE title = :title"),
                    {"title": title}
                ).fetchone()
                if existing:
                    existing_content = existing.content or ""
                    if len(existing_content) < 1000 and naver_link:
                        full_content = extract_full_content(naver_link)
                        if full_content and len(full_content) > len(existing_content):
                            conn.execute(
                                text("UPDATE news SET content = :content, link = :link, naver_link = :naver_link WHERE id = :id"),
                                {"content": full_content, "link": link, "naver_link": naver_link, "id": existing.id}
                            )
                            conn.commit()
                    continue

            # 4. 본문 전체 추출
            full_content = extract_full_content(naver_link)
            if not full_content:
                full_content = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")

            # 5. 이미지 URL 추출
            actual_image_url = extract_image_from_url(naver_link)

            # 6. 데이터베이스 저장 (행 단위 커밋으로 동일 실행 내 중복 방지)
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT IGNORE INTO news (title, content, source, image_url, link, naver_link, status, category_id)
                        VALUES (:title, :content, :source, :image_url, :link, :naver_link, 'published', :category_id)
                    """),
                    {
                        "title": title,
                        "content": full_content,
                        "source": source,
                        "image_url": actual_image_url,
                        "link": link,
                        "naver_link": naver_link,
                        "category_id": category_id,
                    }
                )
                conn.commit()
            total_saved += 1

    return total_saved