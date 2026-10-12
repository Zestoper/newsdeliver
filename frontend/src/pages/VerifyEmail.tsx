import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { CircleX } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

// 인증 메일의 링크가 이 페이지로 온다 — 들어오자마자 인증을 처리한다
export default function VerifyEmail() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [failed, setFailed] = useState(false)
  const sent = useRef(false)
  const token = params.get('token') ?? ''

  useEffect(() => {
    if (sent.current) return
    sent.current = true
    if (!token) { setFailed(true); return }
    api('/api/v1/verify-email', { method: 'POST', body: { token } })
      .then(() => navigate('/subscribe?verified=1', { replace: true }))
      .catch(() => setFailed(true))
  }, [token, navigate])

  return (
    <Layout title="이메일 인증">
      <main className="main-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <div className="center-card">
          {failed ? (
            <>
              <div style={{ fontSize: 48, marginBottom: 20, color: '#fa5252', display: 'flex', justifyContent: 'center' }}><CircleX size="1em" /></div>
              <h2>유효하지 않은 링크</h2>
              <p>인증 링크가 만료되었거나 올바르지 않습니다.<br />구독 페이지에서 다시 시도해주세요.</p>
              <Link to="/subscribe" className="primary-link">구독 페이지로 이동</Link>
            </>
          ) : (
            <>
              <span className="server-wake-spinner dark" />
              <h2>이메일 인증 중이에요</h2>
              <p>잠시만 기다려주세요.</p>
            </>
          )}
        </div>
      </main>
    </Layout>
  )
}
