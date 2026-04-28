-- NewsDelivery 전체 스키마
-- 생성 순서: 의존성 없는 테이블 → 외래키 참조 테이블

-- ──────────────────────────────────────────────
-- 1. 사용자
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news_users (
    id            VARCHAR(20)  PRIMARY KEY,
    name          VARCHAR(20)  NOT NULL,
    birth         DATE,
    pw            VARCHAR(255) NULL,
    email         VARCHAR(50)  UNIQUE,
    tel           VARCHAR(20),
    role          VARCHAR(20)  DEFAULT 'user',
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    oauth_provider VARCHAR(20) NULL,
    oauth_id      VARCHAR(100) NULL,
    press_approved   TINYINT(1) DEFAULT 0,
    press_notified   TINYINT(1) DEFAULT 0,
    CONSTRAINT chk_role CHECK (role IN ('user', 'admin', 'press')),
    UNIQUE KEY oauth_unique (oauth_provider, oauth_id)
);

-- ──────────────────────────────────────────────
-- 2. 카테고리
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
    id   INT         AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

INSERT IGNORE INTO categories (name) VALUES
    ('정치'), ('경제'), ('사회'), ('문화'), ('스포츠'),
    ('IT'), ('국제'), ('연예'), ('예술');

-- ──────────────────────────────────────────────
-- 3. 뉴스
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news (
    id          INT          AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    content     LONGTEXT     NOT NULL,
    image_url   VARCHAR(500),
    source      VARCHAR(255),
    status      VARCHAR(20)  DEFAULT 'draft',
    category_id INT,
    author_id   VARCHAR(20),
    view_count  INT          DEFAULT 0,
    ai_summary  TEXT         NULL,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_status CHECK (status IN ('draft', 'published')),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (author_id)   REFERENCES news_users(id),
    UNIQUE INDEX unique_title (title(191))
);

-- ──────────────────────────────────────────────
-- 4. 구독
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id           INT          AUTO_INCREMENT PRIMARY KEY,
    user_id      VARCHAR(20)  NOT NULL,
    email        VARCHAR(50)  NOT NULL,
    is_active    BOOLEAN      DEFAULT TRUE,
    is_verified  TINYINT(1)   DEFAULT 0,
    verify_token VARCHAR(100),
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES news_users(id)
);

-- ──────────────────────────────────────────────
-- 5. 카테고리 구독
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS category_subscriptions (
    id          INT         AUTO_INCREMENT PRIMARY KEY,
    user_id     VARCHAR(20) NOT NULL,
    category_id INT         NOT NULL,
    FOREIGN KEY (user_id)     REFERENCES news_users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    UNIQUE KEY unique_cat_sub (user_id, category_id)
);

-- ──────────────────────────────────────────────
-- 6. 이메일 발송 로그
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_logs (
    id               INT      AUTO_INCREMENT PRIMARY KEY,
    news_id          INT      NOT NULL,
    sent_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    recipient_count  INT      DEFAULT 0,
    FOREIGN KEY (news_id) REFERENCES news(id)
);

-- ──────────────────────────────────────────────
-- 7. 뉴스레터 발송 기록 (중복 방지)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS newsletter_sent (
    id      INT          AUTO_INCREMENT PRIMARY KEY,
    email   VARCHAR(255) NOT NULL,
    news_id INT          NOT NULL,
    sent_at DATETIME     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_sent (email, news_id)
);

-- ──────────────────────────────────────────────
-- 8. 좋아요
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news_likes (
    id         INT         AUTO_INCREMENT PRIMARY KEY,
    news_id    INT         NOT NULL,
    user_id    VARCHAR(20) NOT NULL,
    created_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES news(id),
    FOREIGN KEY (user_id) REFERENCES news_users(id),
    UNIQUE KEY unique_like (news_id, user_id)
);

-- ──────────────────────────────────────────────
-- 9. 댓글
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news_comments (
    id         INT         AUTO_INCREMENT PRIMARY KEY,
    news_id    INT         NOT NULL,
    user_id    VARCHAR(20) NOT NULL,
    content    TEXT        NOT NULL,
    parent_id  INT         DEFAULT NULL,
    created_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES news(id),
    FOREIGN KEY (user_id) REFERENCES news_users(id)
);

-- ──────────────────────────────────────────────
-- 10. 댓글 좋아요
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comment_likes (
    id         INT         AUTO_INCREMENT PRIMARY KEY,
    comment_id INT         NOT NULL,
    user_id    VARCHAR(50) NOT NULL,
    UNIQUE KEY unique_comment_like (comment_id, user_id)
);

-- ──────────────────────────────────────────────
-- 11. 북마크
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bookmarks (
    id         INT         AUTO_INCREMENT PRIMARY KEY,
    user_id    VARCHAR(50) NOT NULL,
    news_id    INT         NOT NULL,
    created_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_bookmark (user_id, news_id)
);

-- ──────────────────────────────────────────────
-- 12. 신고
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    news_id       INT          NOT NULL,
    reporter_id   VARCHAR(50)  NOT NULL,
    reporter_name VARCHAR(100) NOT NULL,
    reason        VARCHAR(500) DEFAULT '',
    status        VARCHAR(20)  DEFAULT 'pending',
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- ──────────────────────────────────────────────
-- 13. 채팅 방
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_rooms (
    id              INT         AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(50) NOT NULL,
    user_name       VARCHAR(100),
    last_message_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user (user_id)
);

-- ──────────────────────────────────────────────
-- 14. 채팅 메시지
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_messages (
    id           INT         AUTO_INCREMENT PRIMARY KEY,
    room_id      INT         NOT NULL,
    sender       VARCHAR(10) NOT NULL,
    message      TEXT        NOT NULL,
    message_type VARCHAR(10) DEFAULT 'text',
    is_read      TINYINT(1)  DEFAULT 0,
    created_at   DATETIME    DEFAULT CURRENT_TIMESTAMP
);
