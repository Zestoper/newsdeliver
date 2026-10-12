import { Link } from 'react-router-dom'
import { excerpt, fmtDate, usableImage } from '../lib/format'
import type { NewsItem } from '../lib/types'

const NoImage = () => (
  <div className="card-img no-img">
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="1.5" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="7" y1="8" x2="17" y2="8" />
      <line x1="7" y1="12" x2="17" y2="12" />
      <line x1="7" y1="16" x2="13" y2="16" />
    </svg>
  </div>
)

export default function NewsCard({ news, showDesc = true, showSource = false }: { news: NewsItem; showDesc?: boolean; showSource?: boolean }) {
  return (
    <Link to={`/news/${news.id}`} className="news-card">
      {usableImage(news.image_url)
        ? <div className="card-img" style={{ backgroundImage: `url('${news.image_url}')` }} />
        : <NoImage />}
      <div className="card-body">
        {news.category_name && <span className="cat-badge">{news.category_name}</span>}
        <h3 className="card-title">{news.title}</h3>
        {showDesc && news.content && <p className="card-desc">{excerpt(news.content)}</p>}
        {showSource && news.source ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="card-date">{fmtDate(news.created_at)}</span>
            <span style={{ fontSize: 11, color: '#888', background: '#f5f5f5', padding: '2px 7px', borderRadius: 10 }}>{news.source}</span>
          </div>
        ) : (
          <span className="card-date">{fmtDate(news.created_at)}</span>
        )}
      </div>
    </Link>
  )
}

// 데이터가 오기 전 자리를 잡아두는 카드
export function NewsCardSkeleton() {
  return (
    <div className="news-card skeleton-card" aria-hidden="true">
      <div className="card-img skeleton" />
      <div className="card-body">
        <span className="skeleton skeleton-line" style={{ width: '30%' }} />
        <span className="skeleton skeleton-line" style={{ width: '90%' }} />
        <span className="skeleton skeleton-line" style={{ width: '70%' }} />
      </div>
    </div>
  )
}

export function NewsGrid({ items, loading, count = 6, showDesc, showSource, empty = '등록된 뉴스가 없습니다.' }: {
  items: NewsItem[] | undefined
  loading: boolean
  count?: number
  showDesc?: boolean
  showSource?: boolean
  empty?: string
}) {
  if (loading && !items) {
    return <div className="news-grid">{Array.from({ length: count }, (_, i) => <NewsCardSkeleton key={i} />)}</div>
  }
  if (!items || items.length === 0) {
    return <div className="empty-state"><p>{empty}</p></div>
  }
  return (
    <div className="news-grid">
      {items.map((n) => <NewsCard key={n.id} news={n} showDesc={showDesc} showSource={showSource} />)}
    </div>
  )
}
