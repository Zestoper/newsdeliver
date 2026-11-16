import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

// 소셜 로그인 후 서버가 /auth/callback#token=... 으로 보내준다.
// 토큰으로 내 정보를 받아 로그인 상태로 만든 뒤 첫 화면으로 이동한다.
export default function AuthCallback() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const done = useRef(false) // 개발 모드(StrictMode)에서 effect 가 두 번 도는 것 방지

  useEffect(() => {
    if (done.current) return
    done.current = true

    const fail = (message: string) =>
      navigate(`/login?oauth_error=${encodeURIComponent(message)}`, { replace: true })

    const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
    // 주소창에서 토큰을 지운다 (뒤로가기·복사로 새지 않게)
    window.history.replaceState(null, '', window.location.pathname)

    if (!token) { fail('로그인 정보를 받지 못했습니다.'); return }
    login(token)
      .then(() => navigate('/', { replace: true }))
      .catch(() => fail('로그인에 실패했습니다. 다시 시도해주세요.'))
  }, [login, navigate])

  return <div style={{ padding: 80, textAlign: 'center', color: '#888' }}>로그인 중...</div>
}
