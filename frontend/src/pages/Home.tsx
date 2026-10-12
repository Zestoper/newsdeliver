import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, CircleCheck, TrendingDown, TrendingUp } from 'lucide-react'
import Layout from '../components/Layout'
import { NewsGrid } from '../components/NewsCard'
import { api } from '../lib/api'
import { AGE_GROUPS, AGE_TAGS, type AgeGroup } from '../lib/age'
import { fmtDate, fmtShort, usableImage } from '../lib/format'
import { backendSso } from '../components/Header'
import type { NewsItem } from '../lib/types'
import { useApi } from '../lib/useApi'

interface HomeData {
  news_items: NewsItem[]
  top_commented: NewsItem[]
  top_liked: NewsItem[]
  top_viewed: NewsItem[]
  big5_news: NewsItem[]
}

function Big5Slider({ items }: { items: NewsItem[] }) {
  const [cur, setCur] = useState(0)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setCur((c) => (c + 1) % items.length), 5000)
    return () => clearInterval(t)
  }, [items.length, tick])
  const go = (i: number) => { setCur((i + items.length) % items.length); setTick((t) => t + 1) }
  return (
    <section className="big5-slider-section">
      <div className="big5-label">BIG5 언론사 주요뉴스</div>
      <div className="big5-slider">
        {items.map((n, i) => (
          <Link key={n.id} to={`/news/${n.id}`} className={`big5-slide${i === cur ? ' active' : ''}`}>
            {usableImage(n.image_url)
              ? <div className="big5-bg" style={{ backgroundImage: `url('${n.image_url}')` }} />
              : <div className="big5-bg big5-no-img" />}
            <div className="big5-overlay" />
            <div className="big5-content">
              <span className="big5-source">{n.source}</span>
              {n.category_name && <span className="big5-cat">{n.category_name}</span>}
              <h2 className="big5-title">{n.title}</h2>
              <p className="big5-date">{fmtDate(n.created_at)}</p>
            </div>
          </Link>
        ))}
      </div>
      <button className="big5-arrow big5-prev" onClick={() => go(cur - 1)} aria-label="이전">&#8249;</button>
      <button className="big5-arrow big5-next" onClick={() => go(cur + 1)} aria-label="다음">&#8250;</button>
      <div className="big5-dots">
        {items.map((n, i) => <span key={n.id} className={`big5-dot${i === cur ? ' active' : ''}`} onClick={() => go(i)} />)}
      </div>
    </section>
  )
}

function AgeSection() {
  const [group, setGroup] = useState<AgeGroup>('teen')
  const [keyword, setKeyword] = useState('')
  const [items, setItems] = useState<NewsItem[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    setItems(null)
    setFailed(false)
    const q = new URLSearchParams({ group, ...(keyword ? { keyword } : {}) })
    api<NewsItem[]>(`/api/age-news?${q}`)
      .then((d) => { if (alive) setItems(d) })
      .catch(() => { if (alive) setFailed(true) })
    return () => { alive = false }
  }, [group, keyword])

  return (
    <section className="news-grid-section" style={{ marginTop: 32 }}>
      <div className="section-header" style={{ marginBottom: 14 }}>
        <h2>연령대별 추천</h2>
        <Link to={`/age-news/${group}`} className="more-link">전체보기 <ArrowRight size="1em" /></Link>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {AGE_GROUPS.map((g) => (
          <button key={g.key} className={`age-tab${group === g.key ? ' active' : ''}`} onClick={() => { setGroup(g.key); setKeyword('') }}>
            {g.label}
          </button>
        ))}
      </div>
      <div className="age-tag-row">
        {AGE_TAGS[group].map((t) => (
          <button
            key={t.keyword}
            className={`age-tag${keyword === t.keyword ? ' active' : ''}`}
            onClick={() => setKeyword((k) => (k === t.keyword ? '' : t.keyword))}
          >
            {t.label}
          </button>
        ))}
      </div>
      {failed
        ? <div style={{ color: '#aaa', fontSize: 14, padding: '20px 0' }}>불러오기 실패</div>
        : <NewsGrid items={items ?? undefined} loading={!items} showDesc={false} empty="해당 카테고리 뉴스가 없습니다." />}
    </section>
  )
}

interface Market {
  KOSPI?: { value: string; change: string; rate: string; state: string }
  KOSDAQ?: { value: string; change: string; rate: string; state: string }
  USD_KRW?: number; EUR_KRW?: number; JPY_KRW?: number; CNY_KRW?: number
}

function changeClass(state: string, change: string) {
  const n = parseFloat((change || '0').replace(/,/g, ''))
  if (state === 'RISE' || n > 0) return 'up'
  if (state === 'FALL' || n < 0) return 'down'
  return 'even'
}

function MarketRow({ name, value, change = '', rate = '', cls = 'even' }: { name: string; value: string; change?: string; rate?: string; cls?: string }) {
  return (
    <div className="market-item">
      <span className="market-name">{name}</span>
      <span className="market-right">
        <span className="market-value">{value}</span>
        <span className={`market-change ${cls}`}>
          {cls === 'up' && <TrendingUp size="1em" />}{cls === 'down' && <TrendingDown size="1em" />} {change}{rate ? ` (${rate}%)` : ''}
        </span>
      </span>
    </div>
  )
}

function MarketBox() {
  const [data, setData] = useState<Market | null>(null)
  const [time, setTime] = useState('--')
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    api<Market>('/api/market')
      .then((d) => {
        setData(d)
        const now = new Date()
        setTime(`${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')} 기준`)
      })
      .catch(() => setFailed(true))
  }, [])
  return (
    <>
      <div className="sidebar-header" style={{ marginTop: 10 }}>
        <span className="sidebar-title">시장 지수</span>
        <span className="sidebar-updated">{time}</span>
      </div>
      <div className="market-list">
        {!data && <div className="market-loading">{failed ? '불러오기 실패' : '불러오는 중...'}</div>}
        {data && (
          <>
            <div className="market-section-label">지수</div>
            {data.KOSPI && <MarketRow name="KOSPI" {...data.KOSPI} cls={changeClass(data.KOSPI.state, data.KOSPI.change)} />}
            {data.KOSDAQ && <MarketRow name="KOSDAQ" {...data.KOSDAQ} cls={changeClass(data.KOSDAQ.state, data.KOSDAQ.change)} />}
            <div className="market-divider" />
            <div className="market-section-label">환율 (원)</div>
            {data.USD_KRW ? <MarketRow name="달러" value={data.USD_KRW.toLocaleString()} /> : null}
            {data.EUR_KRW ? <MarketRow name="유로" value={data.EUR_KRW.toLocaleString()} /> : null}
            {data.JPY_KRW ? <MarketRow name="100엔" value={data.JPY_KRW.toLocaleString()} /> : null}
            {data.CNY_KRW ? <MarketRow name="위안" value={data.CNY_KRW.toLocaleString()} /> : null}
          </>
        )}
      </div>
    </>
  )
}

function PopularList({ items, kind }: { items: NewsItem[]; kind: 'like' | 'comment' }) {
  return (
    <div className="news-list">
      {items.map((n) => (
        <Link key={n.id} to={`/news/${n.id}`} className="news-list-item">
          <div className="list-info">
            {n.category_name && <span className="cat-badge small">{n.category_name}</span>}
            <h4 className="list-title">{n.title}</h4>
            <span className="list-date">
              {kind === 'like'
                ? <svg width="12" height="12" viewBox="0 0 20 20" fill="#c00" style={{ verticalAlign: -1 }}><path d="M10 17s-8-5.5-8-10a5 5 0 0110 0 5 5 0 0110 0c0 4.5-8 10-8 10z" /></svg>
                : <svg width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="#888" strokeWidth="2" style={{ verticalAlign: -1 }}><path d="M18 13a2 2 0 01-2 2H6l-4 4V4a2 2 0 012-2h12a2 2 0 012 2z" /></svg>}
              {' '}{kind === 'like' ? n.like_count : n.comment_count}
              &nbsp;·&nbsp;{fmtDate(n.created_at)}
            </span>
          </div>
        </Link>
      ))}
    </div>
  )
}

function Modal({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: '#fff', borderRadius: 16, padding: '40px 36px', maxWidth: 400, width: '90%', textAlign: 'center', boxShadow: '0 8px 40px rgba(0,0,0,0.18)', animation: 'popIn 0.25s ease' }}>
        {children}
      </div>
    </div>
  )
}

const modalBtn: React.CSSProperties = { borderRadius: 8, padding: '12px 24px', fontSize: 14, fontWeight: 700, fontFamily: 'inherit', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', cursor: 'pointer', border: 'none' }

export default function Home() {
  const { data, loading } = useApi<HomeData>('/api/v1/home')
  const [params, setParams] = useSearchParams()
  const closeModal = () => setParams({}, { replace: true })
  const ticker = data?.news_items.slice(0, 15).map((n) => ({ id: n.id, title: n.title }))

  return (
    <Layout ticker={ticker}>
      <div className="main-with-sidebar">
        <main className="main-content">
          {data && data.big5_news.length > 0 && <Big5Slider items={data.big5_news} />}
          {loading && !data && <div className="big5-slider-section skeleton" style={{ minHeight: 360 }} />}

          <section className="news-grid-section">
            <div className="section-header">
              <h2>최신 뉴스</h2>
              <Link to="/news" className="more-link">전체보기 <ArrowRight size="1em" /></Link>
            </div>
            <NewsGrid items={data?.news_items.slice(1, 7)} loading={loading} />
          </section>

          <AgeSection />

          <section className="category-section">
            <div className="popular-grid">
              <div className="popular-col">
                <div className="section-header"><h2>좋아요 많은 뉴스</h2></div>
                {data ? <PopularList items={data.top_liked} kind="like" /> : <ListSkeleton />}
              </div>
              <div className="popular-col">
                <div className="section-header"><h2>댓글 많은 뉴스</h2></div>
                {data ? <PopularList items={data.top_commented} kind="comment" /> : <ListSkeleton />}
              </div>
            </div>
          </section>
        </main>

        <div className="right-col">
          <div className="sidebar-sticky">
            <div className="sidebar-header">
              <span className="sidebar-title">실시간 인기뉴스</span>
              <span className="sidebar-updated">조회수 기준</span>
            </div>
            <ol className="sidebar-list">
              {(data?.top_viewed ?? []).map((n, i) => (
                <li key={n.id} className="sidebar-item">
                  <Link to={`/news/${n.id}`} className="sidebar-link">
                    <span className={`sidebar-rank${i === 0 ? ' rank-1' : i < 3 ? ' rank-top' : ''}`}>{i + 1}</span>
                    <span className="sidebar-news-info">
                      <span className="sidebar-news-title">{n.title}</span>
                      {n.created_at && <span className="sidebar-news-time">{fmtShort(n.created_at)}</span>}
                    </span>
                  </Link>
                </li>
              ))}
              {!data && Array.from({ length: 6 }, (_, i) => (
                <li key={i} className="sidebar-item"><span className="skeleton skeleton-line" style={{ width: '90%', margin: '10px 0' }} /></li>
              ))}
            </ol>
            <MarketBox />
          </div>
        </div>
      </div>

      {params.get('signup_done') === '1' && (
        <Modal>
          <div style={{ fontSize: 52, marginBottom: 16, color: '#2f9e44', display: 'flex', justifyContent: 'center' }}><CircleCheck size="1em" /></div>
          <h2 style={{ fontSize: 20, fontWeight: 900, color: '#1a1a1a', marginBottom: 10 }}>회원가입이 완료됐습니다!</h2>
          <p style={{ fontSize: 14, color: '#555', lineHeight: 1.7, marginBottom: 28 }}>로그인 후 서비스를 이용하실 수 있습니다.</p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button onClick={closeModal} style={{ ...modalBtn, background: '#e9ecef', color: '#333' }}>취소</button>
            <Link to="/login" style={{ ...modalBtn, background: '#D42B2B', color: '#fff' }}>로그인</Link>
          </div>
        </Modal>
      )}
      {params.get('press_notice') === '1' && (
        <Modal>
          <h2 style={{ fontSize: 20, fontWeight: 900, color: '#1a1a1a', marginBottom: 10 }}>언론사 승인이 완료됐습니다!</h2>
          <p style={{ fontSize: 14, color: '#555', lineHeight: 1.7, marginBottom: 28 }}>
            관리자가 회원님의 언론사 계정을 승인했습니다.<br />이제 기사를 작성하고 발행할 수 있습니다.
          </p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button onClick={closeModal} style={{ ...modalBtn, background: '#e9ecef', color: '#333' }}>닫기</button>
            <a href={backendSso('/press/news')} style={{ ...modalBtn, background: '#D42B2B', color: '#fff' }}>글쓰기 시작하기</a>
          </div>
        </Modal>
      )}
    </Layout>
  )
}

function ListSkeleton() {
  return (
    <div className="news-list">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="news-list-item"><span className="skeleton skeleton-line" style={{ width: '85%' }} /></div>
      ))}
    </div>
  )
}

