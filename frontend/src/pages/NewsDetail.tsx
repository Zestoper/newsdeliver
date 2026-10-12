import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CornerDownLeft, CornerDownRight, Eye, FileText, Heart } from 'lucide-react'
import Layout from '../components/Layout'
import { api, form } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmtDate, fmtLong, usableImage } from '../lib/format'
import type { NewsItem } from '../lib/types'
import { useApi } from '../lib/useApi'
import '../styles/detail.css'

interface Detail {
  news: NewsItem & { content: string; link?: string | null; author_id?: string | null }
  like_count: number
  liked: boolean
  bookmarked: boolean
  related_news: NewsItem[]
  can_delete: boolean
}

interface Comment {
  id: number
  content: string
  created_at: string
  user_id: string
  parent_id: number | null
  name: string
  like_count: number
  liked: boolean
}

const REPORT_REASONS = ['허위 정보', '스팸/광고', '혐오 표현', '저작권 침해', '기타']

const smallBtn: React.CSSProperties = { padding: '4px 10px', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontFamily: 'inherit' }

function ArticleBody({ content }: { content: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [collapsible, setCollapsible] = useState(false)
  const [expanded, setExpanded] = useState(false)

  // 긴 기사만 접어서 보여주고 "전체 기사 보기" 버튼을 띄운다
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const full = el.scrollHeight
    el.classList.add('collapsed')
    const collapsed = el.clientHeight
    el.classList.remove('collapsed')
    setCollapsible(full > collapsed + 4)
  }, [content])

  const paras = content.split('\n').map((p) => p.trim()).filter(Boolean)
  return (
    <div className="detail-content-wrap">
      <div ref={ref} className={`detail-content${collapsible && !expanded ? ' collapsed' : ''}`}>
        {paras.map((p, i) => <p key={i}>{p}</p>)}
      </div>
      {collapsible && !expanded && (
        <div className="btn-read-more-wrap">
          <button className="btn-read-more" onClick={() => setExpanded(true)}>전체 기사 보기</button>
        </div>
      )}
    </div>
  )
}

function CommentItem({ c, isReply, newsId, myId, onChange }: {
  c: Comment; isReply: boolean; newsId: number; myId: string | null; onChange: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(c.content)
  const [replyOpen, setReplyOpen] = useState(false)
  const [reply, setReply] = useState('')
  const [like, setLike] = useState({ liked: c.liked, count: c.like_count })
  const mine = !!myId && String(c.user_id) === String(myId)

  const toggleLike = async () => {
    if (!myId) { alert('로그인이 필요합니다.'); return }
    const d = await api<{ success: boolean; liked: boolean; count: number }>(`/news/${newsId}/comments/${c.id}/like`, { method: 'POST' })
    if (d.success) setLike({ liked: d.liked, count: d.count })
  }
  const save = async () => {
    await api(`/news/${newsId}/comments/${c.id}`, { method: 'PUT', body: form({ content: draft }) })
    setEditing(false)
    onChange()
  }
  const remove = async () => {
    if (!confirm('댓글을 삭제할까요?')) return
    await api(`/news/${newsId}/comments/${c.id}`, { method: 'DELETE' })
    onChange()
  }
  const submitReply = async () => {
    if (!reply.trim()) return
    const d = await api<{ success: boolean }>(`/news/${newsId}/comments`, { method: 'POST', body: form({ content: reply, parent_id: c.id }) })
    if (d.success) { setReply(''); setReplyOpen(false); onChange() }
  }

  return (
    <div className="comment-item" style={isReply ? { marginLeft: 32, paddingLeft: 16, borderLeft: '3px solid #f0f0f0' } : undefined}>
      <div className="comment-header">
        <span className="comment-author">{isReply && <><CornerDownRight size="1em" /> </>}{c.name}</span>
        <span className="comment-date">{c.created_at}</span>
      </div>
      {editing ? (
        <div className="comment-edit-box">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            style={{ width: '100%', padding: 8, border: '1.5px solid #dee2e6', borderRadius: 6, fontSize: 14, fontFamily: 'inherit' }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <button onClick={save} className="btn-comment" style={{ padding: '6px 14px' }}>저장</button>
            <button onClick={() => { setEditing(false); setDraft(c.content) }} style={{ ...smallBtn, padding: '6px 14px', background: '#f1f3f5', borderRadius: 6 }}>취소</button>
          </div>
        </div>
      ) : (
        <p className="comment-content">{c.content}</p>
      )}
      <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center' }}>
        {!isReply && (
          <button
            onClick={toggleLike}
            style={{
              ...smallBtn, background: 'none', borderRadius: 20, display: 'flex', alignItems: 'center', gap: 3,
              border: `1px solid ${like.liked ? '#faa2c1' : '#dee2e6'}`, color: like.liked ? '#e64980' : '#adb5bd',
            }}
          >
            <Heart size="1em" fill={like.liked ? 'currentColor' : 'none'} /> {like.count}
          </button>
        )}
        {!isReply && myId && (
          <button onClick={() => setReplyOpen((o) => !o)} style={{ ...smallBtn, background: 'none', color: '#868e96' }}>
            <CornerDownLeft size="1em" /> 답글
          </button>
        )}
        {mine && (
          <>
            <button onClick={() => setEditing(true)} style={{ ...smallBtn, background: '#f1f3f5' }}>수정</button>
            <button onClick={remove} style={{ ...smallBtn, background: '#fff5f5', color: '#fa5252' }}>삭제</button>
          </>
        )}
      </div>
      {replyOpen && (
        <div style={{ marginTop: 10, marginLeft: 32, display: 'flex', gap: 8 }}>
          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            placeholder="답글을 입력하세요"
            style={{ flex: 1, padding: '8px 12px', border: '1.5px solid #dee2e6', borderRadius: 8, fontSize: 14, fontFamily: 'inherit', resize: 'none', height: 56 }}
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button onClick={submitReply} className="btn-comment" style={{ padding: '6px 14px', fontSize: 13 }}>등록</button>
            <button onClick={() => setReplyOpen(false)} style={{ ...smallBtn, padding: '6px 14px', fontSize: 13, background: '#f1f3f5', borderRadius: 6 }}>취소</button>
          </div>
        </div>
      )}
    </div>
  )
}

function Comments({ newsId }: { newsId: number }) {
  const { user } = useAuth()
  const [list, setList] = useState<Comment[] | null>(null)
  const [text, setText] = useState('')

  const load = useCallback(() => {
    api<Comment[]>(`/news/${newsId}/comments`).then(setList).catch(() => setList([]))
  }, [newsId])
  useEffect(load, [load])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    const d = await api<{ success: boolean }>(`/news/${newsId}/comments`, { method: 'POST', body: form({ content: text }) })
    if (d.success) { setText(''); load() }
  }

  const parents = (list ?? []).filter((c) => !c.parent_id)
  const replies = (list ?? []).filter((c) => c.parent_id)

  return (
    <div className="comment-box">
      <h3>댓글</h3>
      {user ? (
        <form className="comment-form" onSubmit={submit}>
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="댓글을 입력하세요" required />
          <button type="submit" className="btn-comment">등록</button>
        </form>
      ) : (
        <p style={{ fontSize: 14, color: '#adb5bd', marginBottom: 16 }}>
          <Link to="/login" style={{ color: '#c00', fontWeight: 600 }}>로그인</Link> 후 댓글을 작성할 수 있습니다.
        </p>
      )}
      <div>
        {list && list.length === 0 && <p style={{ color: '#bbb', fontSize: 14 }}>첫 댓글을 남겨보세요!</p>}
        {parents.map((c) => (
          <div key={c.id}>
            <CommentItem c={c} isReply={false} newsId={newsId} myId={user?.id ?? null} onChange={load} />
            {replies.filter((r) => r.parent_id === c.id).map((r) => (
              <CommentItem key={r.id} c={r} isReply newsId={newsId} myId={user?.id ?? null} onChange={load} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function ReportModal({ newsId, onClose }: { newsId: number; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const submit = async () => {
    try {
      const d = await api<{ success: boolean; message?: string }>(`/news/${newsId}/report`, { method: 'POST', body: form({ reason: reason.trim() }) })
      alert(d.message || (d.success ? '신고가 접수되었습니다.' : '오류가 발생했습니다.'))
    } catch (e) {
      alert((e as Error).message)
    }
    onClose()
  }
  return (
    <div style={{ display: 'flex', position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 9999, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'white', borderRadius: 12, padding: '32px 28px', width: '100%', maxWidth: 420, boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
        <h3 style={{ fontSize: 17, fontWeight: 800, marginBottom: 6 }}>게시글 신고</h3>
        <p style={{ fontSize: 13, color: '#868e96', marginBottom: 20 }}>신고 사유를 선택하거나 직접 입력해주세요.</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
          {REPORT_REASONS.map((r) => (
            <button key={r} className="report-reason-btn" onClick={() => setReason(r)}>{r}</button>
          ))}
        </div>
        <textarea
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="신고 사유를 입력하세요 (선택)"
          style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #dee2e6', borderRadius: 8, fontSize: 14, fontFamily: 'inherit', resize: 'none', marginBottom: 16 }}
        />
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '9px 20px', background: '#f1f3f5', border: 'none', borderRadius: 6, fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>취소</button>
          <button onClick={submit} style={{ padding: '9px 20px', background: '#c00', color: 'white', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>신고하기</button>
        </div>
      </div>
    </div>
  )
}

export default function NewsDetail() {
  const { id } = useParams()
  const newsId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data, loading, error } = useApi<Detail>(`/api/v1/news/${newsId}`)
  const [like, setLike] = useState<{ liked: boolean; count: number } | null>(null)
  const [saved, setSaved] = useState<boolean | null>(null)
  const [copied, setCopied] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)

  useEffect(() => {
    setLike(null)
    setSaved(null)
    window.scrollTo(0, 0)
  }, [newsId])

  const liked = like?.liked ?? data?.liked ?? false
  const likeCount = like?.count ?? data?.like_count ?? 0
  const isSaved = saved ?? data?.bookmarked ?? false

  const needLogin = () => { alert('로그인이 필요합니다.'); navigate('/login') }
  const toggleLike = async () => {
    if (!user) return needLogin()
    const d = await api<{ success: boolean; liked: boolean; count: number }>(`/news/${newsId}/like`, { method: 'POST' })
    if (d.success) setLike({ liked: d.liked, count: d.count })
  }
  const toggleBookmark = async () => {
    if (!user) return needLogin()
    const d = await api<{ success: boolean; saved: boolean }>(`/news/${newsId}/bookmark`, { method: 'POST' })
    if (d.success) setSaved(d.saved)
  }
  const copyUrl = () => {
    navigator.clipboard.writeText(location.href).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }
  const remove = async () => {
    if (!confirm('삭제할까요?')) return
    try {
      await api(`/api/v1/news/${newsId}`, { method: 'DELETE' })
      navigate('/')
    } catch (e) {
      alert((e as Error).message)
    }
  }

  const news = data?.news
  return (
    <Layout title={news?.title ?? '뉴스'}>
      <div className="pg-detail">
        <div className="detail-container">
          {loading && !data && (
            <div className="detail-box">
              <span className="skeleton skeleton-line" style={{ width: '20%' }} />
              <span className="skeleton skeleton-line" style={{ width: '90%', height: 28, margin: '16px 0' }} />
              <span className="skeleton skeleton-line" style={{ width: '30%' }} />
              <div className="skeleton" style={{ height: 320, borderRadius: 8, margin: '24px 0' }} />
              {Array.from({ length: 6 }, (_, i) => <span key={i} className="skeleton skeleton-line" style={{ width: `${90 - i * 5}%` }} />)}
            </div>
          )}
          {error && <p className="detail-empty">뉴스를 찾을 수 없습니다.</p>}

          {news && (
            <>
              <div className="detail-box">
                <span className="detail-source">{news.source || '출처 없음'}</span>
                <h1 className="detail-title">{news.title}</h1>
                <p className="detail-date">{fmtLong(news.created_at)}</p>
                {news.link && (
                  <p className="detail-source-link">
                    출처: <a href={news.link} target="_blank" rel="noopener noreferrer">{news.link}</a>
                  </p>
                )}
                <hr className="detail-divider" />
                {news.image_url && <img src={news.image_url} className="detail-image" alt={news.title} />}

                <ArticleBody content={news.content} />

                <div className="detail-meta">
                  <span className="meta-item"><Heart size="1em" fill="currentColor" /> {likeCount}</span>
                  <span className="meta-item"><Eye size="1em" /> {news.view_count ?? 0}</span>
                </div>

                <div className="detail-actions">
                  <button className={`btn-like${liked ? ' liked' : ''}`} onClick={toggleLike}>
                    <Heart size="1em" fill={liked ? 'currentColor' : 'none'} /> <span>{likeCount}</span>
                  </button>
                  <button
                    className="btn-share"
                    onClick={copyUrl}
                    style={copied ? { background: '#d3f9d8', color: '#2f9e44', borderColor: '#8ce99a' } : undefined}
                  >
                    {copied ? '복사됨' : 'URL 복사'}
                  </button>
                  {user && (
                    <button className={`btn-bookmark${isSaved ? ' saved' : ''}`} onClick={toggleBookmark}>
                      {isSaved ? '저장됨' : '스크랩'}
                    </button>
                  )}
                  {user && data.can_delete && <button className="btn-delete" onClick={remove}>삭제</button>}
                  {user && user.role !== 'admin' && (
                    <button className="btn-report" onClick={() => setReportOpen(true)}>신고</button>
                  )}
                </div>
              </div>

              <Comments newsId={newsId} />

              {data.related_news.length > 0 && (
                <div className="related-box">
                  <h3>관련 뉴스</h3>
                  <div className="related-grid">
                    {data.related_news.map((r) => (
                      <Link key={r.id} to={`/news/${r.id}`} className="related-card">
                        {usableImage(r.image_url)
                          ? <div className="related-img" style={{ backgroundImage: `url('${r.image_url}')` }} />
                          : <div className="related-img related-no-img"><FileText size="1em" /></div>}
                        <div className="related-info">
                          {r.category_name && <span className="related-cat">{r.category_name}</span>}
                          <p className="related-title">{r.title}</p>
                          <span className="related-meta"><Eye size="1em" /> {r.view_count ?? 0} · {fmtDate(r.created_at)}</span>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      {reportOpen && <ReportModal newsId={newsId} onClose={() => setReportOpen(false)} />}
    </Layout>
  )
}
