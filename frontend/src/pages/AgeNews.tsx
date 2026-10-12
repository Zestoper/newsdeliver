import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import Layout from '../components/Layout'
import { NewsGrid } from '../components/NewsCard'
import Pagination from '../components/Pagination'
import { AGE_GROUPS, AGE_TAGS, type AgeGroup } from '../lib/age'
import type { NewsItem } from '../lib/types'
import { useApi } from '../lib/useApi'

interface AgeData { group_label: string; news_items: NewsItem[]; page: number; total_pages: number; total: number }

export default function AgeNews() {
  const { group = 'teen' } = useParams()
  const [params] = useSearchParams()
  const keyword = params.get('keyword') ?? ''
  const page = Math.max(1, Number(params.get('page')) || 1)
  const valid = (AGE_GROUPS as readonly { key: string }[]).some((g) => g.key === group)
  const q = new URLSearchParams({ page: String(page), ...(keyword ? { keyword } : {}) })
  const { data, loading } = useApi<AgeData>(valid ? `/api/v1/age-news/${group}?${q}` : null)
  if (!valid) return <Navigate to="/age-news/teen" replace />
  const kwQs = keyword ? `&keyword=${encodeURIComponent(keyword)}` : ''

  return (
    <Layout title={data?.group_label ?? '연령대별 추천'}>
      <main className="main-content">
        <div className="page-title-bar">
          <h2>연령대별 추천 뉴스</h2>
          <Link to="/" className="more-link" style={{ fontSize: 13 }}><ArrowLeft size="1em" /> 홈으로</Link>
        </div>

        <div className="category-tabs" style={{ marginBottom: 20 }}>
          {AGE_GROUPS.map((g) => (
            <Link key={g.key} to={`/age-news/${g.key}`} className={`cat-tab${group === g.key ? ' active' : ''}`}>{g.label}</Link>
          ))}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 20, alignItems: 'center' }}>
          <Link to={`/age-news/${group}`} className={`age-filter-tag${!keyword ? ' active' : ''}`}>전체</Link>
          {AGE_TAGS[group as AgeGroup].map((t) => (
            <Link
              key={t.keyword}
              to={`/age-news/${group}?keyword=${encodeURIComponent(t.keyword)}`}
              className={`age-filter-tag${keyword === t.keyword ? ' active' : ''}`}
            >
              {t.label}
            </Link>
          ))}
        </div>

        <div style={{ fontSize: 13, color: '#888', marginBottom: 16, minHeight: 20 }}>
          {data && <>총 <strong style={{ color: '#1a1a1a' }}>{data.total}</strong>건의 뉴스</>}
          {data && keyword && <> · <span style={{ color: '#c00' }}>「{keyword}」</span> 검색결과</>}
        </div>

        <NewsGrid items={loading ? undefined : data?.news_items} loading={loading} count={9} showDesc={false} empty="해당 조건의 뉴스가 없습니다." />

        {data && <Pagination page={data.page} totalPages={data.total_pages} href={(p) => `/age-news/${group}?page=${p}${kwQs}`} />}
      </main>
    </Layout>
  )
}
