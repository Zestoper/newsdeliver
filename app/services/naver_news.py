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
}

def extract_full_content(url):
    try:
        with httpx.Client(timeout=5, follow_redirects=True) as client:
            res = client.get(url)
            if res.status_code != 200:
                return None

            html = res.text
            for div_id in ['dic_area', 'articleBodyContents', 'articleBody']:
                idx = html.find(f'id="{div_id}"')
                if idx == -1:
                    continue
                tag_end = html.find('>', idx)
                if tag_end == -1:
                    continue
                # Extract up to 15000 chars after the opening tag — avoids stopping at first nested </div>
                raw = html[tag_end + 1:tag_end + 15000]
                raw = re.sub(r'<(script|style)[^>]*>[\s\S]*?</(script|style)>', '', raw)
                text = re.sub(r'<[^>]+>', '', raw)
                text = re.sub(r'\s+', ' ', text).strip()
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
                    if len(existing_content) < 300 and naver_link:
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