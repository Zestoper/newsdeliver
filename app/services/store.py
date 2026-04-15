news_items = [
    {
        "title": "아침 브리핑: 오늘의 주요 헤드라인",
        "summary": "하루를 빠르게 시작할 수 있도록 핵심 뉴스만 간단하게 정리했습니다.",
        "category": "Daily Brief",
    },
    {
        "title": "IT 트렌드: 생성형 AI 서비스 경쟁 심화",
        "summary": "기업들이 생산성과 개인화 기능을 강화하며 새로운 사용자 경험을 내놓고 있습니다.",
        "category": "Technology",
    },
    {
        "title": "라이프: 주말에 읽기 좋은 문화 뉴스 모음",
        "summary": "영화, 전시, 도서 소식을 한 번에 볼 수 있는 큐레이션 콘텐츠입니다.",
        "category": "Culture",
    },
]

users = []
subscriptions = []


def get_news_items() -> list[dict]:
    return news_items


def is_duplicate_user(*, user_id: str, email: str) -> bool:
    return any(user["user_id"] == user_id or user["email"] == email for user in users)


def add_user(user: dict) -> None:
    users.append(user)


def is_duplicate_subscription(email: str) -> bool:
    return email in subscriptions


def add_subscription(email: str) -> None:
    subscriptions.append(email)
