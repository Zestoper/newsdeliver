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

insert into news_users(id,name,birth,pw,email,tel,role)
values('wnsdud9949','박준영','2000-12-05','1234',
'zestoper@naver.com','01012341234','admin');

select * from news_users;