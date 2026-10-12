import { useCallback, useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, CircleHelp, Clock, CreditCard, Handshake, Mail, MessageSquare, Paperclip, TriangleAlert, X, type LucideIcon } from 'lucide-react'
import Layout from '../components/Layout'
import { api, API_BASE, getToken, mediaUrl } from '../lib/api'
import { useAuth } from '../lib/auth'
import '../styles/contact.css'

interface Room {
  id: number
  category: string | null
  last_message_at: string | null
  last_msg: string | null
  unread: number
}

interface Msg {
  sender: 'user' | 'admin'
  message: string
  msg_type: 'text' | 'image' | 'video'
  is_read: boolean
  created_at: string
}

const CATEGORIES: { key: string; label: string; icon: LucideIcon }[] = [
  { key: '일반문의', label: '일반 문의', icon: MessageSquare },
  { key: '구독/결제', label: '구독/결제', icon: CreditCard },
  { key: '오류신고', label: '오류 신고', icon: TriangleAlert },
  { key: '언론사 제휴', label: '언론사 제휴', icon: Handshake },
  { key: '기타', label: '기타', icon: CircleHelp },
]

function catIcon(cat: string | null): LucideIcon {
  return CATEGORIES.find((c) => c.key === cat)?.icon ?? MessageSquare
}

function isBusinessHours(): boolean {
  const now = new Date()
  const t = now.getHours() * 60 + now.getMinutes()
  return t >= 9 * 60 + 30 && t <= 18 * 60 + 30
}

// 백엔드 주소(http/https)를 웹소켓 주소(ws/wss)로 바꾼다
function wsUrl(roomId: number): string {
  const base = API_BASE.replace(/^http/, 'ws')
  return `${base}/api/chat/ws/${roomId}?token=${encodeURIComponent(getToken() ?? '')}`
}

type View = 'rooms' | 'categories' | 'chat'

function ChatModal({ onClose }: { onClose: () => void }) {
  const [view, setView] = useState<View>('rooms')
  const [rooms, setRooms] = useState<Room[] | null>(null)
  const [room, setRoom] = useState<{ id: number; category: string } | null>(null)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  const closeWs = () => {
    wsRef.current?.close()
    wsRef.current = null
  }

  const showRooms = useCallback(async () => {
    closeWs()
    setView('rooms')
    setRoom(null)
    setRooms(null)
    try {
      setRooms(await api<Room[]>('/api/chat/my-rooms'))
    } catch {
      setRooms([])
    }
  }, [])

  useEffect(() => {
    showRooms()
    return closeWs
  }, [showRooms])

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight })
  }, [msgs])

  const openRoom = async (id: number, category: string) => {
    closeWs()
    setRoom({ id, category })
    setView('chat')
    setMsgs([])
    try {
      setMsgs(await api<Msg[]>(`/api/chat/room/${id}/messages`))
    } catch {
      // 기록을 못 불러와도 새 메시지는 주고받을 수 있게 둔다
    }
    const ws = new WebSocket(wsUrl(id))
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      if (d.type === 'read_receipt' && d.reader === 'admin') {
        setMsgs((prev) => prev.map((m) => (m.sender === 'user' ? { ...m, is_read: true } : m)))
      }
      if (d.type === 'message') {
        setMsgs((prev) => [...prev, { sender: d.sender, message: d.message, msg_type: d.msg_type ?? 'text', is_read: false, created_at: d.created_at }])
        if (d.sender === 'admin') api(`/api/chat/room/${id}/read`, { method: 'POST' }).catch(() => {})
      }
    }
    wsRef.current = ws
  }

  const selectCategory = async (category: string) => {
    try {
      const d = await api<{ room_id: number }>(`/api/chat/room?category=${encodeURIComponent(category)}`)
      openRoom(d.room_id, category)
    } catch {
      alert('채팅방을 열지 못했어요. 잠시 후 다시 시도해주세요.')
    }
  }

  const send = (message: string, msgType: Msg['msg_type'] = 'text') => {
    const ws = wsRef.current
    if (!message || !ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ message, msg_type: msgType }))
  }

  const sendText = () => {
    send(input.trim())
    setInput('')
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.nativeEvent.isComposing) sendText()
  }

  const sendFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !room) return
    if (file.size > 30 * 1024 * 1024) { alert('파일 크기는 30MB 이하만 가능합니다.'); return }
    const fd = new FormData()
    fd.append('file', file)
    try {
      const d = await api<{ url: string; type: Msg['msg_type'] }>(`/api/chat/room/${room.id}/upload`, { method: 'POST', body: fd })
      send(d.url, d.type)
    } catch (err) {
      alert(`업로드 실패: ${(err as Error).message}`)
    }
  }

  const title = view === 'chat' && room ? room.category : view === 'categories' ? '문의 유형 선택' : '1:1 채팅 문의'

  return (
    <div className="chat-modal" role="dialog" aria-label="1:1 채팅 문의">
      <div className="chat-modal-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {view !== 'rooms' && (
            <button className="chat-icon-btn" onClick={showRooms} aria-label="뒤로"><ArrowLeft size={20} /></button>
          )}
          <div>
            <div className="chat-modal-title">{title}</div>
            <div className="chat-modal-sub">관리자가 확인 후 답변드립니다</div>
          </div>
        </div>
        <button className="chat-icon-btn" onClick={onClose} aria-label="닫기"><X size={20} /></button>
      </div>

      {view === 'chat' && !isBusinessHours() && (
        <div className="chat-hours-notice">
          <Clock size="1em" /> 상담 가능 시간은 평일 09:30~18:30입니다. 메시지를 남기시면 운영 시간 내 답변드립니다.
        </div>
      )}

      {view === 'rooms' && (
        <div className="chat-pane">
          <div className="chat-scroll" style={{ padding: 10 }}>
            {rooms === null && <div className="chat-empty">불러오는 중...</div>}
            {rooms?.length === 0 && <div className="chat-empty">아직 문의 내역이 없습니다.</div>}
            {rooms?.map((r) => {
              const Icon = catIcon(r.category)
              return (
                <button key={r.id} className="chat-room" onClick={() => openRoom(r.id, r.category || '일반문의')}>
                  <div className="chat-room-top">
                    <span className="chat-room-cat"><Icon size="1em" /> {r.category || '일반문의'}</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {r.unread > 0 && <span className="chat-room-unread">{r.unread}</span>}
                      <span className="chat-room-time">{r.last_message_at ?? ''}</span>
                    </span>
                  </div>
                  <div className="chat-room-last">{r.last_msg || '메시지 없음'}</div>
                </button>
              )
            })}
          </div>
          <div className="chat-foot">
            <button className="chat-primary" onClick={() => setView('categories')}>+ 새 문의 시작하기</button>
          </div>
        </div>
      )}

      {view === 'categories' && (
        <div className="chat-pane" style={{ padding: 20, gap: 12, overflowY: 'auto' }}>
          <p style={{ fontSize: 13, color: '#555' }}>문의 유형을 선택해주세요</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {CATEGORIES.map((c, i) => (
              <button
                key={c.key}
                className="cat-btn"
                style={i === CATEGORIES.length - 1 ? { gridColumn: 'span 2' } : undefined}
                onClick={() => selectCategory(c.key)}
              >
                <c.icon size={22} strokeWidth={1.75} />
                <span>{c.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {view === 'chat' && (
        <div className="chat-pane">
          <div className="chat-scroll chat-messages" ref={boxRef}>
            {msgs.map((m, i) => {
              const mine = m.sender === 'user'
              return (
                <div key={i} className={`chat-msg ${mine ? 'mine' : 'theirs'}`}>
                  {m.msg_type === 'image' ? (
                    <a href={mediaUrl(m.message)} target="_blank" rel="noreferrer">
                      <img src={mediaUrl(m.message)} alt="첨부 이미지" className="chat-media" loading="lazy" />
                    </a>
                  ) : m.msg_type === 'video' ? (
                    <video src={mediaUrl(m.message)} controls className="chat-media" />
                  ) : (
                    <div className="chat-bubble">{m.message}</div>
                  )}
                  <span className="chat-meta">
                    {mine
                      ? <span style={{ color: m.is_read ? '#16a34a' : '#aaa' }}>{m.is_read ? '읽음' : '안읽음'}</span>
                      : <span>관리자</span>}
                    <span>{m.created_at}</span>
                  </span>
                </div>
              )
            })}
          </div>
          <div className="chat-foot chat-input-row">
            <label className="chat-attach" title="사진/동영상 첨부">
              <Paperclip size={16} />
              <input type="file" accept="image/*,video/mp4,video/webm,video/quicktime" onChange={sendFile} hidden />
            </label>
            <input
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder="메시지를 입력하세요..."
              maxLength={500}
            />
            <button className="chat-send" onClick={sendText}>전송</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Contact() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    if (!user) return
    const check = () => api<{ count: number }>('/api/chat/unread').then((d) => setUnread(d.count)).catch(() => {})
    check()
    const t = setInterval(check, 15000)
    return () => clearInterval(t)
  }, [user])

  return (
    <Layout title="문의하기">
      <div className="pg-contact">
        <div className="contact-wrap">
          <div className="contact-title-bar">
            <h2>문의하기</h2>
          </div>

          <div className="contact-cards">
            <div className="contact-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div className="contact-card-icon"><MessageSquare size="1em" /></div>
                <h3>1:1 채팅 문의</h3>
                <p>관리자에게 실시간으로 문의하세요.</p>
              </div>
              {user ? (
                <button className="chat-open-btn" onClick={() => { setOpen(true); setUnread(0) }}>
                  <MessageSquare size="1em" /> 채팅 시작하기
                  {unread > 0 && <span className="chat-open-badge">{unread}</span>}
                </button>
              ) : (
                <Link to="/login" className="chat-open-btn">로그인 후 이용 가능합니다</Link>
              )}
            </div>
            <div className="contact-card">
              <div className="contact-card-icon"><Mail size="1em" /></div>
              <h3>이메일 문의</h3>
              <p>
                궁금한 점은 아래 이메일로 연락 주세요.<br />
                <a href="mailto:zestoper@naver.com">zestoper@naver.com</a>
              </p>
            </div>
          </div>

          <div className="contact-notice">
            <h3>이메일 문의 안내</h3>
            <ul>
              <li>뉴스 구독 및 해지 관련 문의는 이메일로 연락해주세요.</li>
              <li>뉴스 콘텐츠 오류 신고는 제목에 [오류신고]를 포함해 보내주세요.</li>
              <li>언론사 제휴 문의는 제목에 [제휴문의]를 포함해 보내주세요.</li>
              <li>회신은 영업일 기준 1~2일 내로 드립니다.</li>
            </ul>
          </div>
        </div>

        {open && user && <ChatModal onClose={() => setOpen(false)} />}
      </div>
    </Layout>
  )
}
