CREATE TABLE news_users (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(20) NOT NULL,
    birth DATE,
    pw VARCHAR(255) NOT NULL,
    email VARCHAR(50) UNIQUE,
    tel VARCHAR(20),
    role VARCHAR(20) DEFAULT 'user',
    CHECK (role IN ('user', 'admin'))
);
ALTER TABLE news ADD COLUMN author_id VARCHAR(20);
ALTER TABLE news ADD FOREIGN KEY (author_id) REFERENCES news_users(id);

CREATE TABLE news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    image_url VARCHAR(500),
    source VARCHAR(255),
    status VARCHAR(20) DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CHECK (status IN ('draft', 'published'))
);

CREATE TABLE subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    email VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES news_users(id)
);

CREATE TABLE email_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    news_id INT NOT NULL,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    recipient_count INT DEFAULT 0,
    FOREIGN KEY (news_id) REFERENCES news(id)
);


ALTER TABLE news_users DROP CONSTRAINT news_users_chk_1;

ALTER TABLE news_users 
MODIFY COLUMN role VARCHAR(20) DEFAULT 'user',
ADD CONSTRAINT news_users_chk_1 
CHECK (role IN ('user', 'admin', 'press'));


select * from news;