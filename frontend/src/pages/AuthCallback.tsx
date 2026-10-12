import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

// 소셜 로그인 후 서버가 /auth/callback#token=... 으로 보내준다
export default function AuthCallback() {
  const { login } = useAuth()
  const navigate = useNavigate()
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
    if (!token) { navigate('/login?social_error=social', { replace: true }); return }
    login(token).then(() => navigate('/', { replace: true }))
  }, [login, navigate])
  return <div style={{ padding: 80, textAlign: 'center', color: '#888' }}>로그인 중...</div>
}
