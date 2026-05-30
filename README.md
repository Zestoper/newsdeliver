# 📰 NewsDeliver

> 뉴스를 자동 수집·요약하고 구독자에게 이메일로 배달하는 풀스택 뉴스 플랫폼

---

## 📌 프로젝트 개요

| 항목         | 내용                                                                            |
| ------------ | ------------------------------------------------------------------------------- |
| 서비스명     | NewsDeliver                                                                     |
| 백엔드       | Python · FastAPI · SQLAlchemy · APScheduler                                     |
| 데이터베이스 | MySQL                                                                           |
| 외부 API     | 네이버 뉴스 API · Groq API (AI 요약) · OAuth (소셜 로그인) · NewsAPI (해외뉴스) |
| 실시간       | WebSocket 채팅                                                                  |
| 배포         | uvicorn                                                                         |

---

## 🚀 주요 기능

### 1. 뉴스 자동 수집

- 네이버 뉴스 API로 9개 카테고리 최신 뉴스 자동 크롤링
    - 정치 / 경제 / IT / 문화 / 스포츠 / 예술 / 연예 / 국제 / 사회
- **2시간마다** APScheduler로 자동 갱신 (서버 시작 시 즉시 1회 실행)
- BeautifulSoup 없이 **정규표현식만으로** 뉴스 본문 전체 추출
- `og:image` 메타태그 파싱으로 대표 이미지 자동 수집
- 중복 방지: `UNIQUE INDEX (news.title)` + 기존 기사 본문 짧으면 업데이트
- **유사 기사 중복 수집 방지**: Jaccard 유사도(0.35) 기반으로 같은 사건 반복 수집 차단
- **포토 기사 필터링**: `[S포토]`, `[포토]`, `[화보]` 접두어 기사 자동 제외

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
- **OAuth 소셜 로그인** 지원: 카카오 / 네이버 / 구글 (`oauth_provider` / `oauth_id`)
- 쿠키 기반 세션 인증

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

### 7. 실시간 채팅 (고객 문의)

- **WebSocket** 기반 실시간 채팅방
- **다중 채팅방**: 사용자별 여러 채팅방 생성 가능
- **문의 카테고리 선택**: 결제 문의 / 시스템 문의 / 계정 문의 / 서비스 이용 문의 / 신고 문의 / 기타 문의
- **업무시간 외 자동 안내**: 평일 09:30~18:30 이외 메시지 발송 시 상담 가능 시간 자동 안내 (6시간 내 중복 방지)
- 이미지 / 영상 파일 첨부 지원 (`message_type` 컬럼)
- 메시지 DB 저장 (재접속 시 히스토리 유지)
- 읽음 처리 및 미읽음 카운트 배지

### 8. 연령대별 맞춤 뉴스

- 회원가입 시 입력한 **생년월일 기반 연령대 자동 감지**
    - 30세 미만 → 10~20대 / 30~49세 → 30~40대 / 50세 이상 → 50~70대
- 홈 화면에서 **"~님 맞춤 뉴스"** 섹션 자동 표시
- 이미 노출된 뉴스 ID 제외(`exclude` 파라미터)로 중복 노출 방지
- 해외뉴스 별도 섹션 (NewsAPI 수집)

### 9. 홈 화면 중복 제거

- 최신 뉴스 60개 수집 후 **Jaccard 유사도(0.35)** 기반 중복 기사 제거 → 상위 20개 표시
- 구두점·한국어 조사 정규화 후 단어 단위 비교
- 같은 사건을 여러 언론사가 중복 보도한 경우 가장 최신 기사 1건만 유지

### 10. 관리자 페이지

- 회원 관리 및 통계 대시보드
- 뉴스 관리: **작성일 범위 필터** + 언론사 필터 동시 적용 (국내/해외 각각)
- 뉴스레터 수동 발송
- 신고 내역 처리
- 언론사 승인 관리
- 채팅 문의 통합 관리 (카테고리 배지 표시)

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
│   │   ├── oauth.py         # 소셜 로그인 (카카오/네이버/구글)
│   │   ├── chat.py          # WebSocket 채팅 + 업무시간 외 자동 안내
│   │   └── pages.py         # HTML 페이지 렌더링 + 중복 제거 + 맞춤 뉴스
│   ├── services/
│   │   ├── naver_news.py    # 네이버 뉴스 수집 + 본문 스크래핑 + 유사 중복 필터
│   │   ├── global_news.py   # 해외뉴스 수집 (NewsAPI + RSS)
│   │   ├── ai_summary.py    # AI 뉴스 요약
│   │   ├── email.py         # 이메일 발송
│   │   └── store.py         # DB 공통 서비스
│   ├── templates/           # Jinja2 HTML 템플릿
│   └── static/              # CSS, JS, 업로드 파일, admin.html
└── requirements.txt
```

---

## 🗄️ 데이터베이스 테이블

| 테이블                   | 설명                                              |
| ------------------------ | ------------------------------------------------- |
| `news_users`             | 회원 정보 (일반 + OAuth + 언론사, 생년월일 포함)  |
| `news`                   | 뉴스 기사 (링크, AI 요약, 조회수, is_global 포함) |
| `categories`             | 뉴스 카테고리 (9개)                               |
| `subscriptions`          | 이메일 구독 (인증 토큰 포함)                      |
| `category_subscriptions` | 카테고리별 구독 설정                              |
| `news_comments`          | 댓글 및 대댓글 (`parent_id`)                      |
| `comment_likes`          | 댓글 좋아요                                       |
| `bookmarks`              | 뉴스 북마크                                       |
| `reports`                | 뉴스 신고                                         |
| `chat_rooms`             | 채팅방 (카테고리 컬럼 포함, 다중 방 지원)         |
| `chat_messages`          | 채팅 메시지 (이미지/영상 포함)                    |
| `newsletter_sent`        | 뉴스레터 발송 이력 (중복 방지)                    |
| `email_logs`             | 이메일 발송 로그                                  |

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

# 해외뉴스 (NewsAPI)
NEWSAPI_KEY=your_newsapi_key

# 결제 (토스페이먼츠, 선택)
TOSS_CLIENT_KEY=your_toss_client_key
TOSS_SECRET_KEY=your_toss_secret_key
SKIP_PAYMENT=true
```

### 3. 서버 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 서버 시작 시 DB 마이그레이션과 뉴스 초기 수집이 자동으로 실행됩니다.

---

## 🔌 주요 API 엔드포인트

| 메서드 | 경로                       | 설명                                             |
| ------ | -------------------------- | ------------------------------------------------ |
| POST   | `/signup`                  | 회원가입                                         |
| POST   | `/login`                   | 로그인                                           |
| GET    | `/api/news`                | 뉴스 목록 조회                                   |
| GET    | `/api/news/{id}`           | 뉴스 상세 조회                                   |
| POST   | `/api/news/{id}/bookmark`  | 북마크 토글                                      |
| POST   | `/api/news/{id}/comments`  | 댓글 작성                                        |
| GET    | `/api/age-news`            | 연령대별 맞춤 뉴스 (`group`, `exclude` 파라미터) |
| GET    | `/api/chat/room`           | 내 채팅방 목록                                   |
| POST   | `/api/chat/room/new`       | 채팅방 생성 (카테고리 필수)                      |
| DELETE | `/api/chat/room/{room_id}` | 채팅방 삭제                                      |
| WS     | `/api/chat/ws/{room_id}`   | WebSocket 채팅                                   |
| GET    | `/api/admin/users`         | 관리자: 회원 목록                                |

---

## ⏰ 스케줄러

| 작업                  | 주기                     |
| --------------------- | ------------------------ |
| 뉴스 자동 수집 (국내) | 2시간마다 + 서버 시작 시 |
| 해외뉴스 수집         | 3시간마다                |
| 뉴스레터 발송         | 매일 07:30 / 18:30 (KST) |

---

## 💬 채팅 업무시간 안내

| 구분        | 시간                                       |
| ----------- | ------------------------------------------ |
| 상담 가능   | 평일 09:30 ~ 18:30                         |
| 업무시간 외 | 자동 안내 메시지 발송 (6시간 내 중복 방지) |
| 주말        | 자동 안내 메시지 발송                      |

---

## 🐛 트러블슈팅

### 뉴스 본문 추출 실패

- **문제**: 언론사마다 HTML 구조가 달라 단일 CSS 셀렉터로 본문 추출 불가
- **해결**: `id` → `class` → `<article>/<main>` → `<p>` 태그 순서로 4단계 폴백 체인 구현. BeautifulSoup 없이 `re` + `httpx`만 사용해 의존성 최소화
- **결과**: 주요 언론사 90%+ 본문 추출 성공

### 뉴스 중복 저장

- **문제**: 카테고리별 수집 시 동일 기사가 여러 카테고리에 중복 저장
- **해결**: `UNIQUE INDEX (news.title)` + 런타임 `seen_titles` Set 이중 방지
- **결과**: 동일 실행 내 중복 0건

### 이메일 중복 발송

- **문제**: 스케줄러 재시작 시 이미 발송된 이메일에 재발송 위험
- **해결**: `newsletter_sent(email, news_id)` UNIQUE KEY로 발송 이력 관리 → DB가 중복 INSERT를 차단
- **결과**: 재발송 완전 차단

### AI 요약 API 전환 (Gemini → Groq)

- **문제 1**: `gemini-1.5-flash` 호출 시 404 반환 (실제 가용 모델명과 불일치)
- **해결 1**: `ListModels` API로 가용 모델 확인 후 `gemini-2.0-flash`로 수정. 그러나 Google Cloud 결제 계정 미연결로 무료 할당량 자체가 비활성화됨
- **문제 2**: Groq 전환 후 `_fetch_news_job`(수집 스레드)과 뉴스레터 발송 스레드가 동시에 Groq 호출 → 분당 한도 초과 (429)
- **해결 2**: `threading.Lock`으로 Groq 호출 전체 직렬화 + 호출 간격 6초 강제(`_MIN_INTERVAL = 6.0`) + 최대 5회 재시도(지수 백오프)
- **결과**: 429 실패 0건

### 뉴스레터 발송 속도 저하

- **문제**: 구독자 2명·카테고리 5개 기준 발송에 수분 이상 소요
- **원인**: SMTP 연결을 이메일마다 새로 맺는 오버헤드 + Groq 동시 호출로 Rate Limit 반복 발생
- **해결**: `send_newsletters_batch`로 SMTP 연결 1회 재사용 + `threading.Lock`으로 Groq 호출 직렬화
- **결과**: 발송 시간 대폭 단축, 429 실패 제거

### 언론사 승인 알림 누락

- **문제**: 관리자 승인 후 언론사 계정에 알림이 전달되지 않는 경우 발생
- **해결**: `press_approved`(승인 여부)와 `press_notified`(알림 발송 여부) 플래그 분리. 승인 시 이메일 발송 후 `press_notified=1` 처리
- **결과**: 알림 누락 0건

### OAuth 사용자 연령대 매핑 오류

- **문제**: 카카오/네이버 OAuth 가입 사용자는 생년월일 미입력으로 `birth = NULL` 저장 → 맞춤 뉴스 섹션 공백
- **해결**: `_calc_age_group` 함수에서 `birth=NULL`이면 `"teen"` 그룹으로 기본값 설정
- **결과**: OAuth 사용자도 항상 맞춤 뉴스 섹션 표시

### Jaccard 유사도 교정 (한국어 처리)

- **문제**: 한국어 조사·구두점이 단어에 붙어 같은 단어라도 집합 교집합 0 발생 → Jaccard = 0.0으로 중복 제거 미작동
- **해결**: `re.sub(r'[^\w\s]', ' ')`로 구두점 제거 + `_PARTICLE_RE`로 한국어 조사 제거 후 비교. 임계값 0.35 고정 (유사 0.36 포착, 다른 각도 0.30 유지)
- **결과**: 동일 사건 다수 언론사 중복 기사는 1건만 노출, 다른 시각의 기사는 유지
