import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, KeyRound, MailCheck, UserSearch } from 'lucide-react'
import { LogoMark } from '../components/Logo'
import { api } from '../lib/api'
import '../styles/login.css'

type Tab = 'id' | 'pw'

// 아이디 찾기 · 비밀번호 찾기 — 결과는 화면이 아니라 가입 이메일로만 보낸다
export default function FindAccount() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'pw' ? 'pw' : 'id'
  const [email, setEmail] = useState('')
  const [userId, setUserId] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = (tab === 'id' ? '아이디 찾기' : '비밀번호 찾기') + ' - News Delivery'
    setSent(null)
    setError(null)
  }, [tab])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const d = await api<{ message: string }>(
        tab === 'id' ? '/api/v1/auth/find-id' : '/api/v1/auth/password-reset/request',
        { method: 'POST', body: tab === 'id' ? { email } : { user_id: userId, email } },
      )
      setSent(d.message)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="pg-login">
      <div className="login-page">
        <div className="login-brand">
          <Link to="/" className="brand-logo" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none' }}>
            <LogoMark bg="rgba(255,255,255,0.2)" border="2px solid rgba(255,255,255,0.5)" />
            <span style={{ fontSize: 22, fontWeight: 900, letterSpacing: '-0.5px', color: '#fff' }}>NewsDeliver</span>
          </Link>
          <h2 className="brand-tagline">계정을 잊으셨나요?</h2>
          <p className="brand-desc">가입할 때 쓴 이메일로<br />안내 메일을 보내 드려요.</p>
        </div>

        <div className="login-box">
          <div className="login-header">
            <h1>{tab === 'id' ? '아이디 찾기' : '비밀번호 찾기'}</h1>
            <p>{tab === 'id' ? '가입 이메일로 아이디를 보내 드려요.' : '아이디와 가입 이메일을 입력하면 재설정 링크를 보내 드려요.'}</p>
          </div>

          <div className="find-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === 'id'} className={tab === 'id' ? 'active' : ''}
              onClick={() => setParams({ tab: 'id' })}>
              <UserSearch size="1em" /> 아이디 찾기
            </button>
            <button type="button" role="tab" aria-selected={tab === 'pw'} className={tab === 'pw' ? 'active' : ''}
              onClick={() => setParams({ tab: 'pw' })}>
              <KeyRound size="1em" /> 비밀번호 찾기
            </button>
          </div>

          {sent ? (
            <div className="find-sent">
              <MailCheck size={36} strokeWidth={1.6} />
              <p>{sent}</p>
              {tab === 'pw' && <p className="find-sub">재설정 링크는 30분 동안 한 번만 쓸 수 있어요.</p>}
              <Link to="/login" className="btn-login find-btn">로그인하러 가기</Link>
            </div>
          ) : (
            <form className="login-form" onSubmit={submit}>
              {error && <div className="message error">{error}</div>}
              {tab === 'pw' && (
                <div className="input-group">
                  <label htmlFor="find_user_id">아이디</label>
                  <input id="find_user_id" type="text" placeholder="아이디를 입력하세요" value={userId}
                    onChange={(e) => setUserId(e.target.value)} required autoComplete="username" />
                </div>
              )}
              <div className="input-group">
                <label htmlFor="find_email">가입 이메일</label>
                <input id="find_email" type="email" placeholder="example@email.com" value={email}
                  onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
              </div>
              <button type="submit" className="btn-login" disabled={busy}>
                {busy ? '보내는 중...' : tab === 'id' ? '아이디 받기' : '재설정 링크 받기'}
              </button>
              <p className="find-note">소셜 로그인으로 가입했다면 로그인 화면의 소셜 로그인 버튼을 이용해 주세요.</p>
            </form>
          )}

          <div className="back-home">
            <Link to="/login"><ArrowLeft size="1em" /> 로그인으로 돌아가기</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
