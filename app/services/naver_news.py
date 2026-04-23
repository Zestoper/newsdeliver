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

def extract_image_from_url(url):
    """
    bs4 없이 정규표현식(re)만 사용하여 og:image를 추출합니다.
    """
    try:
        # follow_redirects=True를 설정해야 네이버 뉴스 등 리다이렉트 페이지 대응이 가능합니다.
        with httpx.Client(timeout=5, follow_redirects=True) as client:
            res = client.get(url)
            if res.status_code != 200:
                return None
            
            # HTML 소스 내 <meta property="og:image" content="..."> 추출
            # 정규식 설명: property가 og:image인 meta 태그의 content 주소를 찾습니다.
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', res.text)
            if not match:
                # 속성 순서가 반대인 경우(content가 먼저 나오는 경우) 대응
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
        # 카테고리 id 가져오기
        categories = conn.execute(text("SELECT * FROM categories")).fetchall()
        category_map = {row.name: row.id for row in categories}

        total_saved = 0

        for category_name, keyword in CATEGORY_KEYWORDS.items():
            category_id = category_map.get(category_name)
            if not category_id:
                continue

            # display 개수를 조절하여 수집량을 정할 수 있습니다.
            url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=date"

            with httpx.Client() as client:
                res = client.get(url, headers=headers)
                if res.status_code != 200:
                    continue
                data = res.json()

            for item in data.get("items", []):
                # 1. 텍스트 정제
                title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
                content = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
                source = extract_press_name(item.get("originallink", ""))
                link = item.get("link", "")

                # 2. 중복 체크
                existing = conn.execute(
                    text("SELECT id FROM news WHERE title = :title"),
                    {"title": title}
                ).fetchone()
                if existing:
                    continue

                # 3. 정규표현식으로 이미지 URL 추출 (bs4 필요 없음)
                actual_image_url = extract_image_from_url(link)

                # 4. 데이터베이스 저장
                conn.execute(
                    text("""
                        INSERT INTO news (title, content, source, image_url, status, category_id)
                        VALUES (:title, :content, :source, :image_url, 'published', :category_id)
                    """),
                    {
                        "title": title,
                        "content": content,
                        "source": source,
                        "image_url": actual_image_url, 
                        "category_id": category_id,
                    }
                )
                total_saved += 1

        conn.commit()

    return total_saved