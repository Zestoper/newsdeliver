import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ShieldAlert } from 'lucide-react'
import { LogoMark } from '../components/Logo'
import { api } from '../lib/api'
import '../styles/login.css'

// 메일로 받은 재설정 링크(/reset-password?token=...)로 들어와 새 비밀번호를 정하는 화면
export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''
  const [valid, setValid] = useState<boolean | null>(null)
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = '비밀번호 재설정 - News Delivery'
    if (!token) { setValid(false); return }
    api<{ valid: boolean }>(`/api/v1/auth/password-reset/check?token=${encodeURIComponent(token)}`)
      .then((d) => setValid(d.valid))
      .catch(() => setValid(false))
  }, [token])

  const mismatch = pw2.length > 0 && pw !== pw2

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (pw !== pw2) { setError('새 비밀번호가 서로 다릅니다.'); return }
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/auth/password-reset/confirm', {
        method: 'POST', body: { token, new_password: pw, new_password_confirm: pw2 },
      })
      navigate('/login?message=' + encodeURIComponent('비밀번호를 바꿨어요. 새 비밀번호로 로그인해 주세요.'))
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
          <h2 className="brand-tagline">새 비밀번호를<br />정해 주세요</h2>
          <p className="brand-desc">비밀번호는 안전하게 암호화되어<br />저장돼요.</p>
        </div>

        <div className="login-box">
          <div className="login-header">
            <h1>비밀번호 재설정</h1>
            <p>8자 이상으로 입력해 주세요.</p>
          </div>

          {valid === null && <p className="find-note">링크를 확인하는 중이에요...</p>}

          {valid === false && (
            <div className="find-sent">
              <ShieldAlert size={36} strokeWidth={1.6} />
              <p>링크가 만료됐거나 이미 사용됐어요.</p>
              <Link to="/find-account?tab=pw" className="btn-login find-btn">비밀번호 찾기 다시 요청</Link>
            </div>
          )}

          {valid && (
            <form className="login-form" onSubmit={submit}>
              {error && <div className="message error">{error}</div>}
              <div className="input-group">
                <label htmlFor="new_pw">새 비밀번호</label>
                <input id="new_pw" type="password" minLength={8} placeholder="8자 이상" value={pw}
                  onChange={(e) => setPw(e.target.value)} required autoComplete="new-password" />
              </div>
              <div className="input-group">
                <label htmlFor="new_pw2">새 비밀번호 확인</label>
                <input id="new_pw2" type="password" minLength={8} placeholder="한 번 더 입력" value={pw2}
                  onChange={(e) => setPw2(e.target.value)} required autoComplete="new-password" />
                {mismatch && <span className="find-warn">비밀번호가 서로 달라요.</span>}
              </div>
              <button type="submit" className="btn-login" disabled={busy || mismatch}>
                {busy ? '바꾸는 중...' : '비밀번호 바꾸기'}
              </button>
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
