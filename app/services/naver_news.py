import httpx
import re
from sqlalchemy import text
from app.database import engine

CLIENT_ID = "FfHWeyVF9kIrojb2OUqs"
CLIENT_SECRET = "VA8fM0eJLn"

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
    '※', '▶', '◆', '■', '☞', '☛',
    'Copyright', 'copyright', 'ⓒ', '무단 전재', '무단전재', '재배포 금지',
    '제보는', '제보하기', '여러분의 제보', '기사제보',
]

def clean_article_text(text: str) -> str:
    # JS/JSON 광고 스크립트 제거
    for marker in _GARBAGE_MARKERS:
        idx = text.find(marker)
        if idx == -1:
            continue
        w = text.rfind('window.', 0, idx + len(marker))
        cut = w if (w != -1 and idx - w < 300) else idx
        prefix = text[:cut]
        ends = [prefix.rfind(e) for e in ['다. ', '요. ', '다.', '요.', '다!', '다?', '. ']]
        last = max(ends)
        text = (prefix[:last + 2] if last >= 0 else prefix).strip()
        break

    # 언론사 면책/저작권/제보 문구 제거 (※ 등 기호 기준)
    for marker in _FOOTER_MARKERS:
        idx = text.find(marker)
        if idx == -1:
            continue
        prefix = text[:idx]
        ends = [prefix.rfind(e) for e in ['다. ', '요. ', '다.', '요.', '다!', '다?', '. ']]
        last = max(ends)
        text = (prefix[:last + 2] if last >= 0 else prefix).strip()
        break

    # 남아있는 window.xxx 제거
    text = re.sub(r'window\.[^\s가-힣]*\s*=\s*[^가-힣]*', '', text)
    text = re.sub(r' {2,}', ' ', text).strip()
    return text


def extract_full_content(url):
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            res = client.get(url)
            if res.status_code != 200:
                return None

            html = res.text
            for div_id in ['dic_area', 'articleBodyContents', 'articleBody', 'article-body', 'news_body']:
                idx = html.find(f'id="{div_id}"')
                if idx == -1:
                    idx = html.find(f"id='{div_id}'")
                if idx == -1:
                    continue
                tag_end = html.find('>', idx)
                if tag_end == -1:
                    continue
                # 충분히 큰 청크로 읽고 태그 제거 후 문장 단위로 정리
                raw = html[tag_end + 1:tag_end + 200_000]
                # script/style 태그 제거
                raw = re.sub(r'<(script|style)[^>]*>[\s\S]*?</(script|style)>', '', raw, flags=re.IGNORECASE)
                # 나머지 HTML 태그 제거
                text = re.sub(r'<[^>]+>', '', raw)
                text = re.sub(r'\s+', ' ', text).strip()
                text = clean_article_text(text)
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
    except Exception as e:
        print(f"이미지 추출 중 오류 발생: {e}")
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

        for category_name, keyword in CATEGORY_KEYWORDS.items():
            category_id = category_map.get(category_name)
            if not category_id:
                continue

            url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=date"

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

                # 2. 중복 체크 — 기존 기사의 본문이 짧으면 업데이트
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
                                text("UPDATE news SET content = :content, link = :link WHERE id = :id"),
                                {"content": full_content, "link": link, "id": existing.id}
                            )
                    continue

                # 3. 본문 전체 추출
                full_content = extract_full_content(naver_link)
                if not full_content:
                    full_content = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")

                # 4. 이미지 URL 추출
                actual_image_url = extract_image_from_url(naver_link)

                # 5. 데이터베이스 저장
                conn.execute(
                    text("""
                        INSERT INTO news (title, content, source, image_url, link, status, category_id)
                        VALUES (:title, :content, :source, :image_url, :link, 'published', :category_id)
                    """),
                    {
                        "title": title,
                        "content": full_content,
                        "source": source,
                        "image_url": actual_image_url,
                        "link": link,
                        "category_id": category_id,
                    }
                )
                total_saved += 1

        conn.commit()

    return total_saved