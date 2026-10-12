import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Newspaper, User as UserIcon } from 'lucide-react'
import { LogoMark } from '../components/Logo'
import { api, API_BASE } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { User } from '../lib/types'
import '../styles/login.css'

const SOCIAL_LABEL: Record<string, string> = { kakao: '카카오', naver: '네이버', google: '구글' }

export default function Login() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const socialError = params.get('social_error')
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(
    socialError
      ? { text: `${SOCIAL_LABEL[socialError] ?? '소셜'} 로그인에 실패했습니다. 앱 키 설정을 확인해주세요.`, type: 'error' }
      : params.get('message') ? { text: params.get('message')!, type: 'success' } : null,
  )
  const [providers, setProviders] = useState({ kakao: false, naver: false, google: false })

  useEffect(() => {
    document.title = '로그인 - News Delivery'
    api<typeof providers>('/api/v1/auth/providers').then(setProviders).catch(() => {})
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const d = await api<{ token: string; user: User; press_notice: boolean }>('/api/v1/auth/login', {
        method: 'POST', body: { user_id: userId, password },
      })
      await login(d.token, d.user)
      navigate(d.press_notice ? '/?press_notice=1' : '/')
    } catch (err) {
      setMsg({ text: (err as Error).message, type: 'error' })
    } finally {
      setBusy(false)
    }
  }

  const hasSocial = providers.kakao || providers.naver || providers.google

  return (
    <div className="pg-login">
      <div className="login-page">
        <div className="login-brand">
          <Link to="/" className="brand-logo" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none' }}>
            <LogoMark bg="rgba(255,255,255,0.2)" border="2px solid rgba(255,255,255,0.5)" />
            <span style={{ fontSize: 22, fontWeight: 900, letterSpacing: '-0.5px', color: '#fff' }}>NewsDeliver</span>
          </Link>
          <h2 className="brand-tagline">세상의 모든 뉴스를<br />한 곳에서</h2>
          <p className="brand-desc">관심 카테고리를 구독하고<br />최신 뉴스를 이메일로 받아보세요.</p>
        </div>

        <div className="login-box">
          <div className="login-header">
            <h1>로그인</h1>
            <p>News Delivery에 오신 것을 환영합니다</p>
          </div>

          {msg && <div className={`message ${msg.type}`}>{msg.text}</div>}

          <form className="login-form" onSubmit={submit}>
            <div className="input-group">
              <label htmlFor="user_id">아이디</label>
              <input id="user_id" type="text" placeholder="아이디를 입력하세요" value={userId} onChange={(e) => setUserId(e.target.value)} required />
            </div>
            <div className="input-group">
              <label htmlFor="password">비밀번호</label>
              <input id="password" type="password" placeholder="비밀번호를 입력하세요" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button type="submit" className="btn-login" disabled={busy}>{busy ? '로그인 중...' : '로그인'}</button>
          </form>

          {hasSocial && (
            <>
              <div className="login-divider"><span>소셜 로그인</span></div>
              <div className="social-login">
                {providers.kakao && (
                  <a href={`${API_BASE}/oauth/kakao`} className="social-btn kakao-btn">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3C6.477 3 2 6.477 2 10.8c0 2.728 1.618 5.13 4.083 6.605L5.04 21l4.5-2.437A11.6 11.6 0 0012 18.6c5.523 0 10-3.477 10-7.8S17.523 3 12 3z" /></svg>
                    카카오 로그인
                  </a>
                )}
                {providers.naver && (
                  <a href={`${API_BASE}/oauth/naver`} className="social-btn naver-btn">
                    <span className="naver-n">N</span>
                    네이버 로그인
                  </a>
                )}
                {providers.google && (
                  <a href={`${API_BASE}/oauth/google`} className="social-btn google-btn">
                    <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" /><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" /><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" /><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" /></svg>
                    구글 로그인
                  </a>
                )}
              </div>
            </>
          )}

          <div className="login-divider"><span>또는</span></div>

          <div className="signup-section">
            <p>아직 계정이 없으신가요?</p>
            <div className="signup-buttons">
              <Link to="/signup" className="signup-btn user-btn"><UserIcon size="1em" /> 일반 회원가입</Link>
              <Link to="/press/signup" className="signup-btn press-btn"><Newspaper size="1em" /> 언론사 회원가입</Link>
            </div>
          </div>

          <div className="back-home">
            <Link to="/"><ArrowLeft size="1em" /> 메인으로 돌아가기</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
