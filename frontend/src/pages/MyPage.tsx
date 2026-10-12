import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { CircleCheck } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDate } from '../lib/format'
import type { NewsItem, User } from '../lib/types'
import { useApi } from '../lib/useApi'
import '../styles/mypage.css'

interface Report { id: number; news_id: number; reason: string; status: string; created_at: string; news_title: string | null }
interface MyData {
  user: User
  subscription: { email: string; is_active: boolean; is_verified: number } | null
  categories: string[]
  liked_news: NewsItem[]
  bookmarked_news: NewsItem[]
  my_reports: Report[]
}

const REPORT_LABEL: Record<string, string> = { resolved: '글유지', deleted: '글삭제', dismissed: '반려' }

function Card({ title, children, style }: { title: string; children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div className="mp-card" style={style}>
      <h3 className="mp-card-title">{title}</h3>
      {children}
    </div>
  )
}

function NewsLinks({ items, empty }: { items: NewsItem[]; empty: string }) {
  if (!items.length) return <p className="mp-empty">{empty}</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {items.map((n) => (
        <Link key={n.id} to={`/news/${n.id}`} className="mp-row">
          <span className="mp-row-title">{n.title}</span>
          <span className="mp-row-date">{fmtDate(n.created_at)}</span>
        </Link>
      ))}
    </div>
  )
}

function Notice({ ok, children }: { ok: boolean; children: ReactNode }) {
  return <p className={`mp-notice ${ok ? 'ok' : 'err'}`}>{children}</p>
}

export default function MyPage() {
  const { user, refresh, logout } = useAuth()
  const navigate = useNavigate()
  const { data } = useApi<MyData>(user ? '/api/v1/mypage' : null)
  const [profile, setProfile] = useState({ name: '', email: '', tel: '' })
  const [profileMsg, setProfileMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [pw, setPw] = useState({ current_pw: '', new_pw: '', new_pw_confirm: '' })
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    const u = data?.user ?? user
    if (u) setProfile({ name: u.name ?? '', email: u.email ?? '', tel: u.tel ?? '' })
  }, [data, user])

  if (!user) return <Navigate to="/login" replace />

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api('/api/v1/mypage', { method: 'PUT', body: profile })
      await refresh()
      setProfileMsg({ ok: true, text: '정보가 수정되었습니다.' })
    } catch (err) {
      setProfileMsg({ ok: false, text: (err as Error).message })
    }
  }
  const changePw = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api('/api/v1/mypage/password', { method: 'POST', body: pw })
      setPw({ current_pw: '', new_pw: '', new_pw_confirm: '' })
      setPwMsg({ ok: true, text: '비밀번호가 변경되었습니다.' })
    } catch (err) {
      setPwMsg({ ok: false, text: (err as Error).message })
    }
  }
  const withdraw = async () => {
    if (!confirm('정말 탈퇴하시겠습니까? 모든 데이터가 삭제됩니다.')) return
    await api('/api/v1/mypage', { method: 'DELETE' })
    logout()
    navigate('/')
  }

  const sub = data?.subscription
  return (
    <Layout title="마이페이지">
      <main className="main-content">
        <div className="page-title-bar"><h2>마이페이지</h2></div>

        <div className="mypage-grid">
          <Card title="내 정보">
            {profileMsg && <Notice ok={profileMsg.ok}>{profileMsg.text}</Notice>}
            <form onSubmit={saveProfile}>
              <label className="mp-label">이름</label>
              <input className="mp-input" type="text" value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
              <label className="mp-label">이메일</label>
              <input className="mp-input" type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} />
              <label className="mp-label">전화번호</label>
              <input className="mp-input" type="tel" value={profile.tel} onChange={(e) => setProfile({ ...profile, tel: e.target.value })} style={{ marginBottom: 20 }} />
              <button type="submit" className="mp-btn" style={{ width: '100%' }}>정보 수정</button>
            </form>
          </Card>

          <Card title="구독 정보">
            <div style={{ marginBottom: 20 }}>
              <p className="mp-sub-label">이메일 구독</p>
              {!data ? <span className="skeleton skeleton-line" style={{ width: '60%' }} /> : sub && sub.is_active ? (
                <p style={{ fontSize: 14, color: '#2f9e44' }}>
                  <CircleCheck size="1em" /> {sub.email}{' '}
                  {sub.is_verified
                    ? <span className="mp-pill ok">인증완료</span>
                    : <span className="mp-pill warn">인증 필요</span>}
                </p>
              ) : (
                <p className="mp-empty">구독 중이 아닙니다. <Link to="/subscribe" style={{ color: '#c00' }}>구독하기</Link></p>
              )}
            </div>
            <div>
              <p className="mp-sub-label">구독 카테고리</p>
              {data && data.categories.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {data.categories.map((c, i) => <span key={`${c}-${i}`} className="mp-cat">{c}</span>)}
                </div>
              ) : data ? (
                <p className="mp-empty">구독한 카테고리가 없습니다. <Link to="/subscribe" style={{ color: '#c00' }}>구독하기</Link></p>
              ) : null}
            </div>
          </Card>
        </div>

        {!user.oauth_provider && (
          <Card title="비밀번호 변경" style={{ marginTop: 24 }}>
            {pwMsg && <Notice ok={pwMsg.ok}>{pwMsg.text}</Notice>}
            <form onSubmit={changePw} style={{ maxWidth: 400 }}>
              <label className="mp-label">현재 비밀번호</label>
              <input className="mp-input" type="password" placeholder="현재 비밀번호 입력" value={pw.current_pw} onChange={(e) => setPw({ ...pw, current_pw: e.target.value })} required />
              <label className="mp-label">새 비밀번호</label>
              <input className="mp-input" type="password" placeholder="8자 이상 입력" value={pw.new_pw} onChange={(e) => setPw({ ...pw, new_pw: e.target.value })} required />
              <label className="mp-label">새 비밀번호 확인</label>
              <input className="mp-input" type="password" placeholder="새 비밀번호 재입력" value={pw.new_pw_confirm} onChange={(e) => setPw({ ...pw, new_pw_confirm: e.target.value })} required style={{ marginBottom: 20 }} />
              <button type="submit" className="mp-btn">비밀번호 변경</button>
            </form>
          </Card>
        )}

        <Card title="좋아요한 뉴스" style={{ marginTop: 24 }}>
          {data ? <NewsLinks items={data.liked_news} empty="좋아요한 뉴스가 없습니다." /> : <span className="skeleton skeleton-line" style={{ width: '70%' }} />}
        </Card>

        <Card title="스크랩한 뉴스" style={{ marginTop: 24 }}>
          {data ? <NewsLinks items={data.bookmarked_news} empty="스크랩한 뉴스가 없습니다." /> : <span className="skeleton skeleton-line" style={{ width: '70%' }} />}
        </Card>

        <Card title="신고 내역" style={{ marginTop: 24 }}>
          {data && data.my_reports.length === 0 && <p className="mp-empty">신고한 내역이 없습니다.</p>}
          {data?.my_reports.map((r) => (
            <div key={r.id} className="mp-report">
              <div style={{ flex: 1, minWidth: 0 }}>
                {r.news_title
                  ? <Link to={`/news/${r.news_id}`} className="mp-report-title">{r.news_title}</Link>
                  : <span style={{ fontSize: 14, color: '#aaa' }}>(삭제된 기사)</span>}
                {r.reason && <span style={{ fontSize: 12, color: '#868e96', marginTop: 3, display: 'block' }}>사유: {r.reason}</span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                <span className={`report-badge ${r.status}`}>{REPORT_LABEL[r.status] ?? '검토중'}</span>
                <span style={{ fontSize: 12, color: '#aaa' }}>{fmtDate(r.created_at)}</span>
              </div>
            </div>
          ))}
        </Card>

        <Card title="회원 탈퇴" style={{ marginTop: 24 }}>
          <p style={{ fontSize: 13, color: '#868e96', marginBottom: 16, lineHeight: 1.6 }}>
            탈퇴 시 계정 및 모든 활동 내역(좋아요, 북마크, 댓글, 구독 정보)이 영구 삭제되며 복구할 수 없습니다.
          </p>
          <button type="button" onClick={withdraw} className="mp-btn outline">회원 탈퇴</button>
        </Card>
      </main>
    </Layout>
  )
}
