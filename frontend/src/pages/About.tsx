import Layout from '../components/Layout'
import { Link } from 'react-router-dom'
import '../styles/about.css'

export default function About() {
  return (
    <Layout title="회사 소개">
      <div className="pg-about">
<div className="about-hero">
  <div className="about-hero-inner">
    <div className="about-hero-eyebrow">Project Overview</div>
    <div className="about-hero-rule"></div>
    <h1>NewsDeliver</h1>
    <div className="about-hero-rule-thin"></div>
    <p className="about-hero-desc">
      Naver News API로 뉴스를 수집하고, Groq LLaMA 3.1이 요약하며,<br />
      하루 두 번 구독자 맞춤 뉴스레터로 전달하는 백엔드 자동화 플랫폼.
    </p>
    <div className="about-hero-tags">
      <span>Python 3.12</span>
      <span>FastAPI</span>
      <span>PostgreSQL</span>
      <span>React</span>
      <span className="hl">Groq LLaMA 3.1</span>
      <span>WebSocket</span>
      <span>OAuth 2.0</span>
    </div>
  </div>
</div>

<div className="about-wrap">

  
  <div className="about-section">
    <div className="about-section-title">About</div>
    <h2>뉴스를 더 스마트하게</h2>
    <p>하루에도 수천 건의 뉴스가 쏟아집니다. NewsDeliver는 네이버 뉴스 API로 9개 카테고리의 최신 기사를 2시간마다 자동 수집하고, AI가 핵심을 요약해 바쁜 일상 속에서도 꼭 필요한 뉴스만 빠르게 확인할 수 있도록 돕습니다.</p>
    <div className="feature-grid">
      <div className="feature-card full-width">
        <div className="feature-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#c00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="7" width="16" height="10" rx="2" /><path d="M8 7V5M12 7V5M16 7V5" /><path d="M8 17v2M12 17v2M16 17v2" /><circle cx="9" cy="12" r="1.2" fill="#c00" stroke="none" /><circle cx="15" cy="12" r="1.2" fill="#c00" stroke="none" /></svg>
        </div>
        <div className="feature-card-body">
          <h3>AI 뉴스 요약</h3>
          <p>Groq AI(LLaMA 3.1)가 긴 기사를 3~4줄로 핵심만 압축합니다. 요약 결과는 DB의 <code style={{ fontSize: '12px', background: '#f5f5f5', padding: '1px 5px', borderRadius: '3px' }}>ai_summary</code> 컬럼에 저장되어 재요청 시 API 재호출 없이 재사용됩니다.</p>
        </div>
      </div>
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#c00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><polyline points="2,4 12,13 22,4" /></svg>
        </div>
        <div className="feature-card-body">
          <h3>맞춤 이메일 뉴스레터</h3>
          <p>관심 카테고리 구독 시 07:30·18:30 자동 발송. 중복 방지 테이블로 같은 기사 재발송 차단.</p>
        </div>
      </div>
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#c00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><polyline points="12,6 12,12 16,14" /></svg>
        </div>
        <div className="feature-card-body">
          <h3>실시간 자동 수집</h3>
          <p>외부 크론이 2시간마다 수집 작업을 호출해 국내·해외 뉴스를 동시 수집. 오분류 기사 재분류 로직도 주기마다 실행.</p>
        </div>
      </div>
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#c00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>
        </div>
        <div className="feature-card-body">
          <h3>실시간 채팅 문의</h3>
          <p>WebSocket 기반 1:1 채팅. 이미지·비디오 파일 업로드 지원, 읽음 상태 실시간 동기화.</p>
        </div>
      </div>
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#c00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z" /></svg>
        </div>
        <div className="feature-card-body">
          <h3>북마크 & 댓글</h3>
          <p>기사 저장, 댓글·대댓글(parent_id) 구조, 댓글 좋아요. 좋아요·댓글 수 기준 인기 기사 집계.</p>
        </div>
      </div>
      <div className="feature-card">
        <div className="feature-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#c00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
        </div>
        <div className="feature-card-body">
          <h3>언론사 기사 작성</h3>
          <p>관리자 승인 후 press 권한 부여. 언론사 계정이 직접 기사를 작성·게시, 신고 처리 시스템 연동.</p>
        </div>
      </div>
    </div>
  </div>

  
  <div className="about-section">
    <div className="about-section-title">AI Pipeline</div>
    <h2>AI 활용 파이프라인</h2>
    <p>단순 AI 도구 사용이 아닌, 뉴스 수집부터 이메일 발송까지 전 과정을 자동화한 백엔드 파이프라인입니다.</p>
    <div className="pipeline-steps">
      <div className="pipeline-step">
        <div className="pipeline-step-num">STEP 01</div>
        <h4>뉴스 자동 수집</h4>
        <p>외부 크론이 2시간마다 수집 엔드포인트를 호출.<br />
        <code>Naver News API</code> + <code>RSS 피드</code> 파싱으로 국내·해외 뉴스를 동시 수집.</p>
      </div>
      <div className="pipeline-step">
        <div className="pipeline-step-num">STEP 02</div>
        <h4>카테고리 자동 분류</h4>
        <p>키워드 스코어링으로 9개 카테고리 자동 분류.<br />
        <code>정치 재분류 로직</code>이 수집 주기마다 오분류 기사를 보정.</p>
      </div>
      <div className="pipeline-step">
        <div className="pipeline-step-num">STEP 03</div>
        <h4>Groq AI 요약</h4>
        <p><code>Groq LLaMA 3.1</code> API로 긴 기사를 3~4줄로 압축.<br />
        DB의 <code>ai_summary</code> 컬럼에 저장해 요청마다 재호출 없이 재사용.</p>
      </div>
      <div className="pipeline-step">
        <div className="pipeline-step-num">STEP 04</div>
        <h4>맞춤 뉴스레터 발송</h4>
        <p>07:30·18:30 자동 발송.<br />
        <code>newsletter_sent</code> 테이블로 중복 방지. 구독자별 카테고리 5건 필터링 후 SMTP 발송.</p>
      </div>
    </div>
  </div>

  
  <div className="about-section">
    <div className="about-section-title">Stats</div>
    <h2>서비스 현황</h2>
    <div className="stats-row">
      <div className="stat-box">
        <div className="stat-num">14</div>
        <div className="stat-label">DB 테이블</div>
      </div>
      <div className="stat-box">
        <div className="stat-num">7</div>
        <div className="stat-label">API 라우터</div>
      </div>
      <div className="stat-box">
        <div className="stat-num">9</div>
        <div className="stat-label">뉴스 카테고리</div>
      </div>
      <div className="stat-box">
        <div className="stat-num">3</div>
        <div className="stat-label">OAuth 제공자</div>
      </div>
    </div>
  </div>

  
  <div className="about-section">
    <div className="about-section-title">Categories</div>
    <h2>9개 카테고리 커버리지</h2>
    <p>정치부터 연예까지 — 관심사에 맞는 카테고리만 골라 구독할 수 있습니다.</p>
    <div className="tech-stack">
      <span className="tech-tag red">정치</span>
      <span className="tech-tag red">경제</span>
      <span className="tech-tag red">IT</span>
      <span className="tech-tag red">문화</span>
      <span className="tech-tag red">스포츠</span>
      <span className="tech-tag red">예술</span>
      <span className="tech-tag red">연예</span>
      <span className="tech-tag red">국제</span>
      <span className="tech-tag red">사회</span>
    </div>
  </div>

  
  <div className="about-section">
    <div className="about-section-title">Values</div>
    <h2>우리가 추구하는 가치</h2>
    <p>NewsDeliver가 뉴스를 전달하는 방식에 담긴 철학입니다.</p>
    <div className="value-list">
      <div className="value-item">
        <h3>정확성</h3>
        <p>신뢰할 수 있는 출처에서 뉴스를 수집합니다. AI 요약도 원문의 맥락을 최대한 보존합니다.</p>
      </div>
      <div className="value-item">
        <h3>효율성</h3>
        <p>바쁜 하루 속에서 중요한 뉴스를 빠르게 파악할 수 있도록, 핵심만 정리해 드립니다.</p>
      </div>
      <div className="value-item">
        <h3>개인화</h3>
        <p>모든 뉴스를 읽을 필요는 없습니다. 관심 카테고리만 구독해 나만의 뉴스 피드를 만드세요.</p>
      </div>
      <div className="value-item">
        <h3>신뢰성</h3>
        <p>언론사 회원은 관리자 승인 후 기사를 게시할 수 있습니다. 검증된 콘텐츠만 제공합니다.</p>
      </div>
    </div>
  </div>

  
  <div className="about-section">
    <div className="about-section-title">Tech Stack</div>
    <h2>사용 기술</h2>
    <p>안정적이고 빠른 서비스를 위해 검증된 기술 스택을 사용합니다.</p>
    <div className="subsection-label">Backend</div>
    <div className="tech-stack">
      <span className="tech-tag red">Python 3.12</span>
      <span className="tech-tag red">FastAPI</span>
      <span className="tech-tag red">SQLAlchemy</span>
      <span className="tech-tag red">Pydantic</span>
      <span className="tech-tag red">APScheduler</span>
      <span className="tech-tag red">WebSocket</span>
    </div>
    <div className="subsection-label">Frontend</div>
    <div className="tech-stack">
      <span className="tech-tag red">React</span>
      <span className="tech-tag red">TypeScript</span>
      <span className="tech-tag red">Vite</span>
      <span className="tech-tag red">React Router</span>
    </div>
    <div className="subsection-label">Database & Infra</div>
    <div className="tech-stack">
      <span className="tech-tag">PostgreSQL</span>
      <span className="tech-tag">Uvicorn</span>
      <span className="tech-tag">Render</span>
      <span className="tech-tag">Vercel</span>
      <span className="tech-tag">SMTP</span>
    </div>
    <div className="subsection-label">AI & External API</div>
    <div className="tech-stack">
      <span className="tech-tag">Groq LLaMA 3.1</span>
      <span className="tech-tag">Naver News API</span>
      <span className="tech-tag">RSS 피드 파서</span>
      <span className="tech-tag">Open-Meteo (날씨)</span>
    </div>
    <div className="subsection-label">Auth & Payment</div>
    <div className="tech-stack">
      <span className="tech-tag">서명 토큰 (Bearer)</span>
      <span className="tech-tag">OAuth 2.0</span>
      <span className="tech-tag">카카오 / 네이버 / 구글</span>
      <span className="tech-tag">Toss Payments</span>
    </div>
  </div>

  
  <div className="about-section">
    <div className="about-section-title">Architecture</div>
    <h2>백엔드 아키텍처</h2>
    <p>FastAPI + PostgreSQL 기반 API 서버와 React SPA 프론트엔드로 나눠 구성한 뉴스 플랫폼입니다. 프론트엔드는 정적 호스팅에서 바로 뜨고 API 서버는 필요할 때 깨어납니다.</p>

    <div className="subsection-label">API Endpoints</div>
    <div className="api-table-wrap">
    <table className="api-table">
      <thead>
        <tr>
          <th style={{ width: '80px' }}>메서드</th>
          <th style={{ width: '260px' }}>엔드포인트</th>
          <th>설명</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><span className="method-badge method-get">GET</span></td>
          <td><code className="endpoint-code">/api/news</code></td>
          <td>뉴스 목록 조회 (최신순, 페이지네이션)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-post">POST</span></td>
          <td><code className="endpoint-code">/api/news</code></td>
          <td>뉴스 등록 (관리자 / 언론사)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-put">PUT</span></td>
          <td><code className="endpoint-code">/api/news/{"{id}"}</code></td>
          <td>뉴스 수정 (부분 업데이트)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-delete">DELETE</span></td>
          <td><code className="endpoint-code">/api/news/{"{id}"}</code></td>
          <td>뉴스 삭제</td>
        </tr>
        <tr>
          <td><span className="method-badge method-ws">WS</span></td>
          <td><code className="endpoint-code">/api/chat/ws/{"{room_id}"}</code></td>
          <td>WebSocket 실시간 채팅 (파일 업로드·읽음 상태)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-get">GET</span></td>
          <td><code className="endpoint-code">/api/age-news</code></td>
          <td>연령대별 맞춤 뉴스 추천 (10대 / 30대 / 50대)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-get">GET</span></td>
          <td><code className="endpoint-code">/api/market</code></td>
          <td>KOSPI · KOSDAQ · 환율 실시간 조회</td>
        </tr>
        <tr>
          <td><span className="method-badge method-post">POST</span></td>
          <td><code className="endpoint-code">/api/v1/auth/login</code></td>
          <td>로그인 후 서명 토큰 발급 (아이디 / 소셜)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-get">GET</span></td>
          <td><code className="endpoint-code">/oauth/{"{provider}"}/callback</code></td>
          <td>OAuth 소셜 로그인 콜백 (카카오 · 네이버 · 구글)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-post">POST</span></td>
          <td><code className="endpoint-code">/news/{"{id}"}/like</code></td>
          <td>좋아요 토글 (로그인 필요)</td>
        </tr>
        <tr>
          <td><span className="method-badge method-post">POST</span></td>
          <td><code className="endpoint-code">/internal/jobs/newsletter</code></td>
          <td>외부 크론이 호출하는 뉴스레터 발송 (비밀 키 필요)</td>
        </tr>
      </tbody>
    </table>
    </div>

    <div className="subsection-label">Database Schema — 14 Tables</div>
    <div className="db-grid">
      <div className="db-table-card core">
        <div className="db-table-name">news</div>
        <div className="db-table-desc">기사 본문, ai_summary, view_count, is_global, UNIQUE(title)</div>
      </div>
      <div className="db-table-card core">
        <div className="db-table-name">news_users</div>
        <div className="db-table-desc">role(user/admin/press), oauth_provider, press_approved</div>
      </div>
      <div className="db-table-card core">
        <div className="db-table-name">subscriptions</div>
        <div className="db-table-desc">이메일 구독, 이메일 인증 토큰 포함</div>
      </div>
      <div className="db-table-card core">
        <div className="db-table-name">category_subscriptions</div>
        <div className="db-table-desc">카테고리별 구독, 국내/해외 분리 (is_global)</div>
      </div>
      <div className="db-table-card">
        <div className="db-table-name">newsletter_sent</div>
        <div className="db-table-desc">중복 발송 방지 — UNIQUE(email, news_id)</div>
      </div>
      <div className="db-table-card">
        <div className="db-table-name">chat_rooms / chat_messages</div>
        <div className="db-table-desc">WebSocket 채팅, message_type, is_read 관리</div>
      </div>
      <div className="db-table-card">
        <div className="db-table-name">news_likes / news_comments</div>
        <div className="db-table-desc">좋아요, 댓글, 대댓글(parent_id), 댓글 좋아요</div>
      </div>
      <div className="db-table-card">
        <div className="db-table-name">bookmarks / reports</div>
        <div className="db-table-desc">북마크 저장, 신고 처리 (pending / resolved)</div>
      </div>
      <div className="db-table-card">
        <div className="db-table-name">categories / email_logs</div>
        <div className="db-table-desc">카테고리 분류 기준, 이메일 발송 이력</div>
      </div>
    </div>
  </div>

  
  <div className="cta-box">
    <h2>지금 바로 시작해보세요</h2>
    <p>무료로 회원가입하고 관심 카테고리를 구독하면<br />매일 아침·저녁 맞춤 뉴스레터가 찾아옵니다.</p>
    <div className="cta-btns">
      <Link to="/signup" className="cta-btn white">무료 회원가입</Link>
      <Link to="/subscribe" className="cta-btn outline">뉴스레터 구독</Link>
    </div>
  </div>

</div>


      </div>
    </Layout>
  )
}
