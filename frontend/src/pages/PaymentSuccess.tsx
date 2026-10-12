import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { api } from '../lib/api'

// 토스 결제창에서 돌아오는 주소 — 서버에 결제 승인을 요청한 뒤 구독 페이지로 보낸다
export default function PaymentSuccess() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const sent = useRef(false)

  useEffect(() => {
    if (sent.current) return
    sent.current = true
    api('/api/v1/subscribe/payment/confirm', {
      method: 'POST',
      body: {
        paymentKey: params.get('paymentKey') ?? '',
        orderId: params.get('orderId') ?? '',
        amount: Number(params.get('amount') ?? 0),
        email: params.get('email') ?? '',
      },
    })
      .then(() => navigate('/subscribe?mail_sent=1', { replace: true }))
      .catch((e: Error) => setError(e.message))
  }, [params, navigate])

  return (
    <Layout title="결제 확인">
      <main className="main-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <div className="center-card">
          {error ? (
            <>
              <h2>결제를 완료하지 못했어요</h2>
              <p>{error}</p>
              <Link to="/subscribe" className="primary-link">구독 페이지로 돌아가기</Link>
            </>
          ) : (
            <>
              <span className="server-wake-spinner dark" />
              <h2>결제를 확인하고 있어요</h2>
              <p>잠시만 기다려주세요.</p>
            </>
          )}
        </div>
      </main>
    </Layout>
  )
}
