import { Link, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { NewsGrid } from '../components/NewsCard'
import Pagination from '../components/Pagination'
import type { NewsPage } from '../lib/types'
import { useApi } from '../lib/useApi'

// 국내 뉴스(/news)와 해외 뉴스(/global-news)가 같은 화면을 쓴다
export default function NewsList({ global = false }: { global?: boolean }) {
  const [params] = useSearchParams()
  const category = params.get('category') ?? ''
  const page = Math.max(1, Number(params.get('page')) || 1)
  const base = global ? '/global-news' : '/news'
  const q = new URLSearchParams({ page: String(page), ...(category ? { category } : {}) })
  const { data, loading, error } = useApi<NewsPage>(`/api/v1${base}?${q}`)
  const title = global ? '해외뉴스' : '뉴스 목록'

  return (
    <Layout title={title}>
      <main className="main-content">
        <div className="page-title-bar">
          <h2>{title}</h2>
          {category && <span className="cat-badge">{category}</span>}
        </div>

        <div className="category-tabs" style={{ marginBottom: 24 }}>
          <Link to={base} className={`cat-tab${!category ? ' active' : ''}`}>전체</Link>
          {(data?.categories ?? []).map((c) => (
            <Link key={c.id} to={`${base}?category=${encodeURIComponent(c.name)}`} className={`cat-tab${category === c.name ? ' active' : ''}`}>
              {c.name}
            </Link>
          ))}
        </div>

        {error
          ? <div className="empty-state"><p>{error}</p></div>
          : <NewsGrid items={loading ? undefined : data?.news_items} loading={loading} count={9} showSource={global} />}

        {data && (
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            href={(p) => `${base}?page=${p}${category ? `&category=${encodeURIComponent(category)}` : ''}`}
          />
        )}
      </main>
    </Layout>
  )
}
