import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSun, Snowflake, Sun, Thermometer, type LucideIcon } from 'lucide-react'
import { api, API_BASE, getToken } from '../lib/api'
import { useAuth } from '../lib/auth'
import { LogoMark } from './Logo'

const NAV = [
  { to: '/', label: '홈', icon: <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2L2 9h2v8h5v-5h2v5h5V9h2L10 2z" /></svg> },
  { to: '/about', label: '소개', icon: <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="10" cy="10" r="8" /><line x1="10" y1="9" x2="10" y2="14" /><circle cx="10" cy="6.5" r="0.8" fill="currentColor" stroke="none" /></svg> },
  { to: '/news', label: '뉴스', icon: <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor"><rect x="2" y="4" width="16" height="2" rx="1" /><rect x="2" y="9" width="16" height="2" rx="1" /><rect x="2" y="14" width="10" height="2" rx="1" /></svg> },
  { to: '/global-news', label: '해외뉴스', icon: <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="10" cy="10" r="8" /><path d="M10 2C10 2 7 6 7 10s3 8 3 8M10 2c0 0 3 4 3 8s-3 8-3 8M2 10h16" /></svg> },
  { to: '/subscribe', label: '구독', icon: <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 2a6 6 0 016 6c0 4 2 5 2 5H2s2-1 2-5a6 6 0 016-6z" /><path d="M8.5 17a1.5 1.5 0 003 0" /></svg> },
  { to: '/search', label: '검색', icon: <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="8.5" cy="8.5" r="5.5" /><line x1="13" y1="13" x2="18" y2="18" /></svg> },
  { to: '/contact', label: '문의', icon: <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="4" width="16" height="13" rx="2" /><polyline points="2,4 10,11 18,4" /></svg> },
]

const CITIES = [
  { name: '서울', lat: 37.5665, lon: 126.978 },
  { name: '부산', lat: 35.1796, lon: 129.0756 },
  { name: '인천', lat: 37.4563, lon: 126.7052 },
  { name: '대구', lat: 35.8714, lon: 128.6014 },
  { name: '대전', lat: 36.3504, lon: 127.3845 },
  { name: '광주', lat: 35.1595, lon: 126.8526 },
  { name: '울산', lat: 35.5384, lon: 129.3114 },
  { name: '제주', lat: 33.4996, lon: 126.5312 },
]

function weatherIcon(code: number | null): LucideIcon {
  if (code === null) return Thermometer
  if (code === 0) return Sun
  if (code <= 3) return CloudSun
  if (code <= 48) return CloudFog
  if (code <= 67) return CloudRain
  if (code <= 77) return Snowflake
  if (code <= 82) return CloudDrizzle
  if (code <= 99) return CloudLightning
  return Cloud
}

interface Weather { name: string; temp: number | string; code: number | null }

// 백엔드와 상관없이 바로 뜨는 날씨 티커 (open-meteo 직접 호출)
function WeatherTicker() {
  const [list, setList] = useState<Weather[]>([])
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    Promise.all(CITIES.map(async (c) => {
      try {
        const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${c.lat}&longitude=${c.lon}&current=temperature_2m,weather_code&timezone=Asia%2FSeoul`)
        const d = await r.json()
        return { name: c.name, temp: Math.round(d.current.temperature_2m), code: d.current.weather_code as number }
      } catch {
        return { name: c.name, temp: '--', code: null }
      }
    })).then(setList)
  }, [])

  useEffect(() => {
    if (!list.length) return
    const t = setInterval(() => setIdx((i) => (i + 1) % list.length), 3000)
    return () => clearInterval(t)
  }, [list])

  const w = list[idx]
  if (!w) return <div className="weather-ticker" />
  const Icon = weatherIcon(w.code)
  return (
    <div
      className="weather-ticker"
      onClick={() => window.open(`https://search.naver.com/search.naver?query=${encodeURIComponent(`${w.name} 날씨`)}`, '_blank')}
    >
      <span className="wt-item" key={w.name}>
        <span className="wt-city">{w.name}</span>
        <span className="wt-icon"><Icon size="1em" /></span>
        <span className="wt-temp">{w.temp}°</span>
      </span>
    </div>
  )
}

function NewsTicker({ items }: { items: { id: number; title: string }[] }) {
  const [idx, setIdx] = useState(0)
  const navigate = useNavigate()
  useEffect(() => {
    if (!items.length) return
    const t = setInterval(() => setIdx((i) => (i + 1) % items.length), 4000)
    return () => clearInterval(t)
  }, [items])
  const item = items[idx % Math.max(items.length, 1)]
  return (
    <div className="news-ticker-pill" onClick={() => item && navigate(`/news/${item.id}`)}>
      {item && (
        <span className="nt-item" key={item.id}>
          <span className="nt-badge">속보</span>
          <span className="nt-title">{item.title}</span>
        </span>
      )}
    </div>
  )
}

const badgeStyle: React.CSSProperties = {
  position: 'absolute', background: '#c00', color: 'white', fontSize: 10, fontWeight: 900,
  minWidth: 16, height: 16, borderRadius: 16, textAlign: 'center', lineHeight: '16px', padding: '0 3px',
}

// 관리자·언론사 페이지는 서버 렌더링으로 남아 있어서, 토큰을 넘겨 쿠키 로그인으로 들어간다
export function backendSso(next: string): string {
  return `${API_BASE}/auth/sso?token=${encodeURIComponent(getToken() ?? '')}&next=${encodeURIComponent(next)}`
}

export default function Header({ ticker }: { ticker?: { id: number; title: string }[] }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // 읽지 않은 문의 수 (로그인했을 때만)
  useEffect(() => {
    if (!user) { setUnread(0); return }
    let alive = true
    const check = () => api<{ count?: number; rooms?: number }>('/api/chat/unread')
      .then((d) => { if (alive) setUnread((user.role === 'admin' ? d.rooms : d.count) ?? 0) })
      .catch(() => {})
    check()
    const t = setInterval(check, 15000)
    return () => { alive = false; clearInterval(t) }
  }, [user])

  const today = new Date()
  const dateText = `${today.getFullYear()}년 ${String(today.getMonth() + 1).padStart(2, '0')}월 ${String(today.getDate()).padStart(2, '0')}일`

  return (
    <header className={`site-header${scrolled ? ' scrolled' : ''}`}>
      <div className="header-top">
        <div className="header-left">
          <div className="header-left-meta">
            <div className="header-date">{dateText}</div>
            <WeatherTicker />
          </div>
          {ticker && ticker.length > 0 && <NewsTicker items={ticker} />}
        </div>
        <div className="header-logo">
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none' }}>
            <LogoMark />
            <span style={{ fontSize: 22, fontWeight: 900, letterSpacing: '-0.5px', color: '#1a1a1a' }}>
              <span style={{ color: '#c00' }}>News</span>Deliver
            </span>
          </Link>
        </div>
        <div className="header-actions">
          {user ? (
            <>
              <span className="user-name">{user.name}님</span>
              <Link to="/mypage" className="header-btn outline">마이페이지</Link>
              {user.role === 'admin' && (
                <a href={backendSso('/admin')} className="header-btn" style={{ position: 'relative' }}>
                  관리자
                  {unread > 0 && <span style={{ ...badgeStyle, background: '#ff4444', top: -8, right: -8 }}>{unread}</span>}
                </a>
              )}
              {user.role === 'press' && <a href={backendSso('/press/news')} className="header-btn">언론사</a>}
              <button
                type="button"
                className="header-btn outline"
                onClick={() => { logout(); navigate('/login?message=' + encodeURIComponent('로그아웃되었습니다.')) }}
              >
                로그아웃
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="header-btn outline">로그인</Link>
              <Link to="/signup" className="header-btn">회원가입</Link>
            </>
          )}
        </div>
      </div>

      <nav className="main-nav">
        <button
          className={`nav-hamburger${open ? ' nav-open' : ''}`}
          aria-label={open ? '메뉴 닫기' : '메뉴 열기'}
          onClick={() => setOpen((o) => !o)}
        >
          <span /><span /><span />
        </button>
        <ul className={open ? 'nav-open' : ''}>
          {NAV.map((n) => (
            <li key={n.to}>
              <NavLink
                to={n.to}
                end
                onClick={() => setOpen(false)}
                style={n.to === '/contact' ? { position: 'relative' } : undefined}
              >
                <span className="nav-icon">{n.icon}</span>
                {n.label}
                {n.to === '/contact' && user && user.role !== 'admin' && unread > 0 && (
                  <span style={{ ...badgeStyle, top: -6, right: -10 }}>{unread}</span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  )
}
