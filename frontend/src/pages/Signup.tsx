import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LogoMark } from '../components/Logo'
import { api } from '../lib/api'
import '../styles/signup.css'

type Errors = Partial<Record<'name' | 'birth' | 'pw' | 'pwConfirm' | 'email' | 'phone', string>>

const phoneBox: React.CSSProperties = { padding: '7px 4px', border: '1.5px solid #e0e0e0', borderRadius: 6, fontSize: 13, textAlign: 'center' }

// 일반 회원가입과 언론사 회원가입이 같은 화면을 쓴다
export default function Signup({ press = false }: { press?: boolean }) {
  const navigate = useNavigate()
  const [f, setF] = useState({ name: '', birth: '', user_id: '', password: '', password_confirm: '', email: '' })
  const [phone, setPhone] = useState(['', '', ''])
  const [errors, setErrors] = useState<Errors>({})
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const p2 = useRef<HTMLInputElement>(null)
  const p3 = useRef<HTMLInputElement>(null)
  const userIdRef = useRef<HTMLInputElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    document.title = `${press ? '언론사 회원가입' : '회원가입'} - News Delivery`
  }, [press])

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((p) => ({ ...p, [k]: e.target.value }))

  // 일반 회원 이름은 한글 5자까지 (조합 중인 글자는 건드리지 않는다)
  const onName = (e: React.ChangeEvent<HTMLInputElement>) => {
    const native = e.nativeEvent as InputEvent
    const v = !press && !native.isComposing ? e.target.value.replace(/[^가-힣]/g, '').slice(0, 5) : e.target.value
    setF((p) => ({ ...p, name: v }))
  }
  const onPhone = (i: number, max: number) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value.replace(/\D/g, '').slice(0, max)
    setPhone((p) => p.map((x, j) => (j === i ? v : x)))
    if (i === 0 && v.length === 3) p2.current?.focus()
    if (i === 1 && v.length === 4) p3.current?.focus()
  }

  const validate = (): boolean => {
    const e: Errors = {}
    if (!press && !/^[가-힣]{1,5}$/.test(f.name)) e.name = '한글만, 5자 이하로 입력해주세요.'
    if (!press && f.birth && f.birth.slice(0, 4) < '1920') e.birth = '1920년 이후 생년월일을 입력해주세요.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) e.email = '올바른 이메일 형식이 아닙니다.'
    if (f.password.length < 8 || !/^[a-zA-Z0-9가-힣.!@]*$/.test(f.password)) e.pw = '8자 이상, 허용된 특수문자(. ! @)만 사용하세요.'
    if (f.password !== f.password_confirm) e.pwConfirm = '비밀번호가 일치하지 않습니다.'
    if (!/^\d{3}-\d{4}-\d{4}$/.test(phone.join('-'))) e.phone = '전화번호를 모두 입력해주세요.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setBusy(true)
    setMsg(null)
    try {
      await api('/api/v1/auth/signup', {
        method: 'POST',
        body: { name: f.name, birth: f.birth, user_id: f.user_id, password: f.password, email: f.email, phone: phone.join('-'), press },
      })
      navigate('/?signup_done=1')
    } catch (err) {
      const text = (err as Error).message
      setMsg(text)
      if (text.includes('아이디')) userIdRef.current?.focus()
      else if (text.includes('이메일')) emailRef.current?.focus()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="pg-signup">
      <div className="signup-page">
        <div className="signup-brand" style={press ? { background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)' } : undefined}>
          <Link to="/" className="brand-logo" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none' }}>
            {press ? <LogoMark /> : <LogoMark bg="rgba(255,255,255,0.2)" border="2px solid rgba(255,255,255,0.5)" />}
            <span style={{ fontSize: 22, fontWeight: 900, letterSpacing: '-0.5px', color: '#fff' }}>
              <span style={{ color: press ? '#ff8080' : '#fff' }}>News</span>Deliver
            </span>
          </Link>
          {press ? (
            <>
              <h2 className="brand-tagline">언론사와 함께<br />뉴스를 전달하세요</h2>
              <p className="brand-desc">직접 뉴스를 작성하고<br />구독자들에게 전달해보세요.</p>
            </>
          ) : (
            <>
              <h2 className="brand-tagline">지금 바로<br />시작하세요</h2>
              <p className="brand-desc">관심 카테고리를 구독하고<br />맞춤 뉴스를 받아보세요.</p>
            </>
          )}
        </div>

        <div className="signup-box">
          <div className="signup-header">
            <h1>{press ? '언론사 회원가입' : '일반 회원가입'}</h1>
            <p>{press ? '뉴스를 작성하고 싶은 언론사라면 가입하세요' : 'News Delivery 계정을 만들어보세요'}</p>
          </div>

          {msg && <div className="message error">{msg}</div>}

          <form className="signup-form" onSubmit={submit} noValidate>
            <div className="form-row">
              <div className="input-group">
                <label htmlFor="name">{press ? '언론사명' : '이름'}</label>
                <input id="name" type="text" placeholder={press ? '언론사 이름을 입력하세요' : '성함을 입력하세요'} value={f.name} onChange={onName} required />
                {!press && <span className="field-hint">한글만, 5자 이하</span>}
                <span className="field-error">{errors.name}</span>
              </div>
              <div className="input-group">
                <label htmlFor="birth">{press ? '설립일' : '생년월일'}</label>
                <input id="birth" type="date" min={press ? undefined : '1920-01-01'} value={f.birth} onChange={set('birth')} required />
                <span className="field-error">{errors.birth}</span>
              </div>
            </div>

            <div className="input-group">
              <label htmlFor="user_id">아이디</label>
              <input id="user_id" ref={userIdRef} type="text" placeholder="사용할 아이디를 입력하세요" value={f.user_id} onChange={set('user_id')} required />
            </div>

            <div className="input-group">
              <label htmlFor="password">비밀번호</label>
              <input id="password" type="password" placeholder="비밀번호 입력" value={f.password} onChange={set('password')} required />
              <span className="field-hint">8자 이상, 특수문자는 . ! @ 만 허용</span>
              <span className="field-error">{errors.pw}</span>
            </div>

            <div className="input-group">
              <label htmlFor="password_confirm">비밀번호 확인</label>
              <input id="password_confirm" type="password" placeholder="비밀번호 재입력" value={f.password_confirm} onChange={set('password_confirm')} required />
              <span className="field-error">{errors.pwConfirm}</span>
            </div>

            <div className="input-group">
              <label htmlFor="email">이메일</label>
              <input id="email" ref={emailRef} type="email" placeholder="example@news.com" value={f.email} onChange={set('email')} required />
              <span className="field-hint">example@domain.com 형식</span>
              <span className="field-error">{errors.email}</span>
            </div>

            <div className="input-group">
              <label>전화번호</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <input type="tel" inputMode="numeric" placeholder="010" value={phone[0]} onChange={onPhone(0, 3)} style={{ ...phoneBox, width: 56 }} />
                <span style={{ color: '#9ca3af', fontWeight: 700 }}>-</span>
                <input ref={p2} type="tel" inputMode="numeric" placeholder="1234" value={phone[1]} onChange={onPhone(1, 4)} style={{ ...phoneBox, width: 68 }} />
                <span style={{ color: '#9ca3af', fontWeight: 700 }}>-</span>
                <input ref={p3} type="tel" inputMode="numeric" placeholder="1234" value={phone[2]} onChange={onPhone(2, 4)} style={{ ...phoneBox, width: 68 }} />
              </div>
              <span className="field-error">{errors.phone}</span>
            </div>

            <button type="submit" className="btn-signup" disabled={busy}>{busy ? '가입 중...' : '회원가입'}</button>
          </form>

          <div className="signup-footer">
            <span>이미 계정이 있으신가요?</span>
            <Link to="/login">로그인</Link>
            <span>|</span>
            {press ? <Link to="/signup">일반 회원가입</Link> : <Link to="/press/signup">언론사로 가입</Link>}
          </div>
        </div>
      </div>
    </div>
  )
}
