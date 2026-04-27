# 📰 NewsDeliver

> 뉴스를 자동 수집·요약하고 구독자에게 이메일로 배달하는 풀스택 뉴스 플랫폼

---

## 📌 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 서비스명 | NewsDeliver |
| 백엔드 | Python · FastAPI · SQLAlchemy · APScheduler |
| 데이터베이스 | MySQL |
| 외부 API | 네이버 뉴스 API · Groq API (AI 요약) · OAuth (소셜 로그인) |
| 실시간 | WebSocket 채팅 |
| 배포 | uvicorn |

---

## 🚀 주요 기능

### 1. 뉴스 자동 수집
- 네이버 뉴스 API로 9개 카테고리 최신 뉴스 자동 크롤링
  - 정치 / 경제 / IT / 문화 / 스포츠 / 예술 / 연예 / 국제 / 사회
- **2시간마다** APScheduler로 자동 갱신 (서버 시작 시 즉시 1회 실행)
- BeautifulSoup 없이 **정규표현식만으로** 뉴스 본문 전체 추출
- `og:image` 메타태그 파싱으로 대표 이미지 자동 수집
- 중복 방지: `UNIQUE INDEX (news.title)` + 기존 기사 본문 짧으면 업데이트

### 2. AI 뉴스 요약
- **Groq API** (`llama-3.1-8b-instant`) 로 뉴스 자동 요약 (`ai_summary` 컬럼)
- 뉴스레터 발송 시 요약 없는 기사만 선별해 생성 — DB 캐시 활용으로 중복 호출 없음
- 스레드 안전 직렬화 + 재시도(최대 5회)로 안정적 생성 보장

### 3. 이메일 뉴스레터
- 구독자에게 하루 **2회** 자동 발송 (07:30 / 18:30 KST)
- 이메일 인증 토큰으로 구독 확인
- 중복 발송 방지 (`newsletter_sent` 테이블) — 새 기사 없는 카테고리는 최근 5개 재발송
- SMTP 연결 1회 재사용으로 빠른 일괄 발송

### 4. 사용자 인증
- 일반 회원가입 / 로그인 (이메일 인증 포함)
- **OAuth 소셜 로그인** 지원 (`oauth_provider` / `oauth_id`)
- JWT 기반 인증

### 5. 언론사 회원 시스템
- 일반 사용자와 분리된 언론사 전용 계정
- 가입 후 **관리자 승인** 프로세스 (`press_approved`)
- 승인 완료 시 알림 발송 (`press_notified`)
- 언론사 전용 기사 작성 / 수정 / 삭제

### 6. 뉴스 상호작용
- 북마크 저장 (`bookmarks`)
- 댓글 및 **대댓글** (`parent_id` 기반 계층 구조)
- 댓글 좋아요 (`comment_likes`)
- 뉴스 신고 (`reports`)
- 조회수 카운트 (`view_count`)

### 7. 실시간 채팅
- **WebSocket** 기반 실시간 채팅방
- 메시지 DB 저장 (재접속 시 히스토리 유지)
- 이미지 메시지 지원 (`message_type` 컬럼)

### 8. 관리자 페이지
- 회원 관리 및 통계 대시보드
- 뉴스레터 수동 발송
- 신고 내역 처리
- 언론사 승인 관리

---

## 🗂️ 프로젝트 구조

```
newsdeliver/
├── app/
│   ├── main.py              # FastAPI 앱 진입점 + DB 마이그레이션 + 스케줄러
│   ├── config.py            # 환경변수 설정
│   ├── database.py          # SQLAlchemy 엔진 및 모델
│   ├── routers/
│   │   ├── users.py         # 회원가입, 로그인, 마이페이지
│   │   ├── news.py          # 뉴스 조회, 검색, 북마크, 댓글
│   │   ├── press.py         # 언론사 기사 작성/수정/삭제
│   │   ├── admin_api.py     # 관리자 API + 뉴스레터 발송
│   │   ├── oauth.py         # 소셜 로그인 (OAuth)
│   │   ├── chat.py          # WebSocket 채팅
│   │   └── pages.py         # HTML 페이지 렌더링
│   ├── services/
│   │   ├── naver_news.py    # 네이버 뉴스 수집 + 본문 스크래핑
│   │   ├── ai_summary.py    # AI 뉴스 요약
│   │   ├── email.py         # 이메일 발송
│   │   └── store.py         # 스토어 관련 서비스
│   ├── templates/           # Jinja2 HTML 템플릿
│   └── static/              # CSS, 업로드 파일
└── requirements.txt
```

---

## 🗄️ 데이터베이스 테이블

| 테이블 | 설명 |
|--------|------|
| `news_users` | 회원 정보 (일반 + OAuth + 언론사) |
| `news` | 뉴스 기사 (링크, AI 요약, 조회수 포함) |
| `categories` | 뉴스 카테고리 |
| `subscriptions` | 이메일 구독 (인증 토큰 포함) |
| `news_comments` | 댓글 및 대댓글 (`parent_id`) |
| `comment_likes` | 댓글 좋아요 |
| `bookmarks` | 뉴스 북마크 |
| `reports` | 뉴스 신고 |
| `chat_rooms` | 채팅방 |
| `chat_messages` | 채팅 메시지 (이미지 포함) |
| `newsletter_sent` | 뉴스레터 발송 이력 (중복 방지) |

---

## ⚙️ 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정 (`.env`)

```env
# 데이터베이스 (MySQL 연결 문자열)
DB_URL=mysql+pymysql://root:비밀번호@localhost:3306/newsdelivery

# 네이버 뉴스 API (뉴스 수집용)
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# 이메일 발송 (뉴스레터 / 인증메일)
SMTP_HOST=smtp.naver.com
SMTP_PORT=587
SMTP_USER=your_email@naver.com
SMTP_PASSWORD=your_smtp_password

# 소셜 로그인 — 카카오
KAKAO_CLIENT_ID=your_kakao_client_id
KAKAO_CLIENT_SECRET=your_kakao_client_secret
KAKAO_REDIRECT_URI=http://localhost:8000/oauth/kakao/callback

# 소셜 로그인 — 네이버 OAuth
NAVER_OAUTH_CLIENT_ID=your_naver_oauth_client_id
NAVER_OAUTH_CLIENT_SECRET=your_naver_oauth_client_secret
NAVER_OAUTH_REDIRECT_URI=http://localhost:8000/oauth/naver/callback

# 소셜 로그인 — 구글
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback

# AI 요약 (Groq API)
GROQ_API_KEY=your_groq_api_key

# 서버
SERVER_BASE_URL=http://127.0.0.1:8000

# 결제 (토스페이먼츠, 선택)
TOSS_CLIENT_KEY=your_toss_client_key
TOSS_SECRET_KEY=your_toss_secret_key
SKIP_PAYMENT=True
```

### 3. 서버 실행



```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

> 서버 시작 시 DB 마이그레이션과 뉴스 초기 수집이 자동으로 실행됩니다.

---

## 🔌 주요 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/users/signup` | 회원가입 |
| POST | `/api/users/login` | 로그인 |
| GET | `/api/news` | 뉴스 목록 조회 |
| GET | `/api/news/{id}` | 뉴스 상세 조회 |
| POST | `/api/news/{id}/bookmark` | 북마크 토글 |
| POST | `/api/news/{id}/comments` | 댓글 작성 |
| POST | `/api/news/{id}/report` | 뉴스 신고 |
| POST | `/api/press/news` | 언론사 기사 작성 |
| GET | `/api/admin/users` | 관리자: 회원 목록 |
| WS | `/ws/chat/{room_id}` | WebSocket 채팅 |

---

## ⏰ 스케줄러

| 작업 | 주기 |
|------|------|
| 뉴스 자동 수집 | 2시간마다 + 서버 시작 시 |
| 뉴스레터 발송 | 매일 07:30 / 18:30 (KST) |
