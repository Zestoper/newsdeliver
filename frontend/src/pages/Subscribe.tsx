import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CircleCheck, Clock, FileText, Info, LayoutGrid, Lock, MailOpen, Sunrise, Sunset, TriangleAlert } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Category } from '../lib/types'
import { useApi } from '../lib/useApi'
import '../styles/subscribe.css'

interface SubState {
  categories: Category[]
  domestic_subscribed_ids: number[]
  global_subscribed_ids: number[]
  current_email: string | null
  is_subscribed: boolean
  is_verified: boolean
  toss_client_key: string
  skip_payment: boolean
}

const CAT_LIST = ['정치', '경제', 'IT', '문화', '스포츠', '예술', '연예', '국제', '사회']
const SUB_PRICE = 2900

declare global {
  interface Window {
    TossPayments?: (key: string) => { requestPayment: (method: string, opts: Record<string, unknown>) => Promise<void> }
  }
}

function loadToss(): Promise<void> {
  if (window.TossPayments) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://js.tosspayments.com/v1/payment'
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('결제 모듈을 불러오지 못했어요.'))
    document.head.appendChild(s)
  })
}

const benefit = (Icon: typeof FileText, title: string, desc: string) => (
  <div className="sub-benefit-card" style={{ background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 10px rgba(0,0,0,0.06)', display: 'flex', gap: 16, alignItems: 'flex-start' }}>
    <div style={{ flexShrink: 0, width: 42, height: 42, background: '#fff0f0', color: '#c00', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}><Icon size="1em" /></div>
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 800, color: '#1a1a1a', margin: '0 0 6px' }}>{title}</h3>
      <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7, margin: 0 }}>{desc}</p>
    </div>
  </div>
)

export default function Subscribe() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const { data, reload, setData } = useApi<SubState>('/api/v1/subscribe')
  const [tab, setTab] = useState<'domestic' | 'global'>('domestic')
  const [result, setResult] = useState<{ text: string; ok: boolean } | null>(null)
  const [email, setEmail] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(() => {
    if (params.get('verified') === '1') return { text: '이메일 인증이 완료되었습니다! 구독이 활성화되었어요.', type: 'success' }
    if (params.get('mail_sent') === '1') return { text: '인증 메일을 발송했어요. 이메일을 확인해 인증을 완료해주세요.', type: 'success' }
    if (params.get('pay_error') === '1') return { text: '결제가 완료되지 않았어요. 다시 시도해주세요.', type: 'error' }
    return null
  })

  const toggleCategory = async (cat: Category, isGlobal: boolean) => {
    const d = await api<{ success: boolean; subscribed: boolean }>(`/categories/${cat.id}/subscribe`, {
      method: 'POST', body: { is_global: isGlobal ? 1 : 0 },
    })
    if (!d.success || !data) return
    const key = isGlobal ? 'global_subscribed_ids' : 'domestic_subscribed_ids'
    const ids = d.subscribed ? [...data[key], cat.id] : data[key].filter((x) => x !== cat.id)
    setData({ ...data, [key]: ids })
    const label = isGlobal ? '해외' : '국내'
    setResult({ text: d.subscribed ? `${label} 구독했어요!` : `${label} 구독 해지했어요.`, ok: d.subscribed })
  }

  const subscribeDirect = async (addr: string) => {
    setBusy(true)
    try {
      await api('/api/v1/subscribe', { method: 'POST', body: { email: addr } })
      setMsg({ text: '인증 메일을 발송했어요. 이메일을 확인해 인증을 완료해주세요.', type: 'success' })
      setEmail(''); setNewEmail('')
      reload()
    } catch (e) {
      setMsg({ text: (e as Error).message, type: 'error' })
    } finally {
      setBusy(false)
    }
  }

  const pay = async (e: FormEvent) => {
    e.preventDefault()
    if (!data) return
    if (data.skip_payment) return subscribeDirect(email.trim())
    try {
      await loadToss()
      const toss = window.TossPayments!(data.toss_client_key)
      const orderId = `sub-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
      await toss.requestPayment('카드', {
        amount: SUB_PRICE,
        orderId,
        orderName: 'News Delivery 뉴스레터 구독',
        successUrl: `${location.origin}/subscribe/payment/success?email=${encodeURIComponent(email.trim())}`,
        failUrl: `${location.origin}/subscribe?pay_error=1`,
        customerEmail: email.trim(),
      })
    } catch (err) {
      const e2 = err as { code?: string; message?: string }
      if (e2.code !== 'USER_CANCEL') alert(`결제 중 오류가 발생했습니다: ${e2.message}`)
    }
  }

  const unsubscribe = async () => {
    if (!confirm('구독을 취소할까요?')) return
    await api('/api/v1/unsubscribe', { method: 'POST' })
    reload()
  }

  const cats = (data?.categories ?? []).filter((c) => CAT_LIST.includes(c.name))
  const subscribedIds = tab === 'global' ? data?.global_subscribed_ids ?? [] : data?.domestic_subscribed_ids ?? []

  return (
    <Layout title="구독하기">
      <div className="pg-subscribe">
        <div className="subscribe-container">
          <h1>구독 서비스</h1>
          <p className="sub-desc">관심 카테고리를 선택하고 이메일을 입력하세요.</p>

          {msg && <div className={`message ${msg.type}`}>{msg.text}</div>}

          {user ? (
            <>
              <div className="news-type-tabs">
                <button className={`type-tab${tab === 'domestic' ? ' active' : ''}`} onClick={() => { setTab('domestic'); setResult(null) }}>국내</button>
                <button className={`type-tab${tab === 'global' ? ' active' : ''}`} onClick={() => { setTab('global'); setResult(null) }}>해외</button>
              </div>

              <div className="category-grid">
                {!data && Array.from({ length: 9 }, (_, i) => <span key={i} className="category-btn skeleton" style={{ minHeight: 44 }} />)}
                {cats.map((c) => (
                  <button key={c.id} className={`category-btn${subscribedIds.includes(c.id) ? ' subscribed' : ''}`} onClick={() => toggleCategory(c, tab === 'global')}>
                    {c.name}
                  </button>
                ))}
              </div>

              <p style={{ marginTop: 12, fontSize: 14, color: result?.ok ? '#2f9e44' : '#868e96', minHeight: 21 }}>{result?.text}</p>

              <div className="email-section-box">
                <p className="sub-desc">뉴스레터를 받을 이메일을 입력하세요.</p>
                {data?.is_subscribed ? (
                  <>
                    <p style={{ fontSize: 14, color: '#2f9e44', marginBottom: 12 }}>
                      <CircleCheck size="1em" /> 현재 구독 중: <strong>{data.current_email}</strong>{' '}
                      {data.is_verified
                        ? <span style={{ background: '#d3f9d8', color: '#2f9e44', padding: '2px 8px', borderRadius: 10, fontSize: 12, whiteSpace: 'nowrap', display: 'inline-block' }}>인증완료</span>
                        : <span style={{ background: '#fff3cd', color: '#856404', padding: '2px 8px', borderRadius: 10, fontSize: 12 }}><TriangleAlert size="1em" /> 인증 필요 — 발송된 이메일을 확인해주세요</span>}
                    </p>
                    <form className="email-form" style={{ marginBottom: 10 }} onSubmit={(e) => { e.preventDefault(); subscribeDirect(newEmail.trim()) }}>
                      <input type="email" placeholder="새 이메일 주소 입력" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} required />
                      <button type="submit" className="btn-subscribe" disabled={busy}>이메일 변경</button>
                    </form>
                    <button type="button" onClick={unsubscribe} className="btn-unsubscribe">구독 취소</button>
                  </>
                ) : (
                  <>
                    <form className="email-form" onSubmit={pay}>
                      <input type="email" placeholder="example@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
                      <button type="submit" className="btn-subscribe" disabled={busy || !data}>
                        {data?.skip_payment ? '인증 메일 받기' : '구독하기'}
                      </button>
                    </form>
                    <p style={{ fontSize: 12, color: '#adb5bd', marginTop: 8 }}>
                      {data?.skip_payment
                        ? '이메일 인증을 완료하면 구독이 활성화됩니다. (테스트 모드 — 결제 생략)'
                        : '월 2,900원 · 결제 후 이메일 인증을 완료하면 구독이 활성화됩니다.'}
                    </p>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="email-section-box" style={{ textAlign: 'center', padding: '48px 32px' }}>
              <div style={{ fontSize: 48, marginBottom: 16, color: '#adb5bd', display: 'flex', justifyContent: 'center' }}><Lock size="1em" /></div>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: '#1a1a1a', marginBottom: 10 }}>로그인이 필요한 서비스입니다</h2>
              <p style={{ fontSize: 14, color: '#777', marginBottom: 28, lineHeight: 1.7 }}>
                뉴스레터 구독과 카테고리 설정을 이용하려면<br />먼저 로그인해주세요.
              </p>
              <Link to="/login" className="login-cta">로그인하기</Link>
              <p style={{ marginTop: 16, fontSize: 13, color: '#adb5bd' }}>
                계정이 없으신가요? <Link to="/signup" style={{ color: '#c00', fontWeight: 600, textDecoration: 'none' }}>회원가입</Link>
              </p>
            </div>
          )}
        </div>

        <div className="sub-info-wrap" style={{ maxWidth: 760, margin: '0 auto 64px', padding: '0 24px' }}>
          <div style={{ marginBottom: 40 }}>
            <p className="sub-eyebrow">Benefits</p>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: '#1a1a1a', margin: '0 0 20px' }}>구독하면 이런 점이 좋아요</h2>
            <div className="sub-benefits-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 16 }}>
              {benefit(FileText, 'AI가 요약한 핵심 뉴스', '긴 기사를 읽을 필요 없이 AI가 3~4줄로 압축한 요약으로 핵심을 빠르게 파악하세요.')}
              {benefit(LayoutGrid, '내 관심사만 골라서', '정치·경제·IT·문화 등 9개 카테고리 중 원하는 것만 선택해 맞춤 뉴스레터를 받아보세요.')}
              {benefit(Clock, '항상 최신 뉴스', '2시간마다 뉴스를 자동 수집해 가장 최신 기사를 이메일로 전달합니다.')}
              {benefit(MailOpen, 'inbox에서 바로 확인', '앱 설치 없이 이메일 하나로 오늘의 뉴스를 바로 확인할 수 있습니다.')}
            </div>
          </div>

          <div style={{ background: 'white', borderRadius: 14, padding: 32, boxShadow: '0 2px 10px rgba(0,0,0,0.06)' }}>
            <p className="sub-eyebrow">Schedule</p>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: '#1a1a1a', margin: '0 0 6px' }}>언제 메일이 오나요?</h2>
            <p style={{ fontSize: 14, color: '#777', margin: '0 0 28px', lineHeight: 1.7 }}>뉴스레터는 하루 두 번, 정해진 시간에 자동으로 발송됩니다.</p>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 200, background: 'linear-gradient(135deg,#fff8e1,#fffde7)', borderRadius: 12, padding: 24, borderLeft: '4px solid #f59f00' }}>
                <div style={{ fontSize: 28, marginBottom: 10, color: '#e67700' }}><Sunrise size="1em" /></div>
                <div style={{ fontSize: 22, fontWeight: 900, color: '#e67700', letterSpacing: '-0.5px', marginBottom: 6 }}>오전 7:30</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#1a1a1a', marginBottom: 4 }}>아침 뉴스레터</div>
                <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7, margin: 0 }}>하루를 시작하기 전, 어젯밤부터 오늘 아침까지의 주요 뉴스를 정리해 드려요.</p>
              </div>
              <div style={{ flex: 1, minWidth: 200, background: 'linear-gradient(135deg,#e8f4fd,#dbeafe)', borderRadius: 12, padding: 24, borderLeft: '4px solid #339af0' }}>
                <div style={{ fontSize: 28, marginBottom: 10, color: '#1971c2' }}><Sunset size="1em" /></div>
                <div style={{ fontSize: 22, fontWeight: 900, color: '#1971c2', letterSpacing: '-0.5px', marginBottom: 6 }}>오후 6:30</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#1a1a1a', marginBottom: 4 }}>저녁 뉴스레터</div>
                <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7, margin: 0 }}>퇴근 후 오늘 하루 있었던 주요 뉴스를 한눈에 확인하세요.</p>
              </div>
            </div>
            <div style={{ marginTop: 20, background: '#f8f9fa', borderRadius: 10, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 18, color: '#868e96' }}><Info size="1em" /></span>
              <p style={{ fontSize: 13, color: '#555', lineHeight: 1.7, margin: 0 }}>
                카테고리별로 최신 뉴스 <strong style={{ color: '#1a1a1a' }}>5건</strong>을 선별해 발송합니다.
                새 기사가 없는 경우에도 최근 기사로 채워 빠짐없이 보내드립니다.
              </p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
