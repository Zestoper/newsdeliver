import httpx
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

            url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=date"

            with httpx.Client() as client:
                res = client.get(url, headers=headers)
                if res.status_code != 200:
                    continue
                data = res.json()

            for item in data.get("items", []):
                title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
                content = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")
                source = item.get("originallink", "")
                link = item.get("link", "")

                # 중복 체크
                existing = conn.execute(
                    text("SELECT id FROM news WHERE title = :title"),
                    {"title": title}
                ).fetchone()
                if existing:
                    continue

                conn.execute(
                    text("""
                        INSERT INTO news (title, content, source, image_url, status, category_id)
                        VALUES (:title, :content, :source, :image_url, 'published', :category_id)
                    """),
                    {
                        "title": title,
                        "content": content,
                        "source": source,
                        "image_url": link,
                        "category_id": category_id,
                    }
                )
                total_saved += 1

        conn.commit()

    return total_saved