import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { excerpt } from '../lib/format'
import type { NewsItem } from '../lib/types'
import { useApi } from '../lib/useApi'
import '../styles/search.css'

interface SearchData { news_items: NewsItem[]; sources: string[] }

const isoDate = (v?: string | null) => (v ? v.slice(0, 10) : '')

export default function Search() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const source = params.get('source') ?? ''
  const [input, setInput] = useState(q)
  const [sel, setSel] = useState(source)
  const qs = new URLSearchParams({ ...(q ? { q } : {}), ...(source ? { source } : {}) })
  const { data, loading } = useApi<SearchData>(`/api/v1/search?${qs}`)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const next = new URLSearchParams({ ...(input.trim() ? { q: input.trim() } : {}), ...(sel ? { source: sel } : {}) })
    navigate(`/search?${next}`)
  }

  return (
    <Layout title="검색">
      <main className="main-content pg-search">
        <div className="search-container">
          <h2>뉴스 검색</h2>
          <form className="search-form" onSubmit={submit}>
            <div className="search-row">
              <input type="text" placeholder="키워드를 입력하세요" value={input} onChange={(e) => setInput(e.target.value)} className="search-input" />
              <select value={sel} onChange={(e) => setSel(e.target.value)} className="search-select">
                <option value="">전체 언론사</option>
                {(data?.sources ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <button type="submit" className="search-btn">검색</button>
            </div>
          </form>

          <div className="search-result-info">
            {(q || source) && data && (
              <p>
                {q && <><strong>"{q}"</strong> </>}
                {source && <>· <strong>{source}</strong> </>}
                검색 결과 <strong>{data.news_items.length}건</strong>
              </p>
            )}
          </div>

          <ul className="search-list">
            {loading && !data && Array.from({ length: 5 }, (_, i) => (
              <li key={i} className="search-item"><span className="skeleton skeleton-line" style={{ width: '80%', margin: 18 }} /></li>
            ))}
            {data?.news_items.map((n) => (
              <li key={n.id} className="search-item">
                <Link to={`/news/${n.id}`}>
                  <div className="search-item-header">
                    <span className="search-source">{n.source || '출처 없음'}</span>
                    <span className="search-date">{isoDate(n.created_at)}</span>
                  </div>
                  <h3 className="search-title">{n.title}</h3>
                  <p className="search-summary">{excerpt(n.content, 120)}</p>
                </Link>
              </li>
            ))}
            {data && data.news_items.length === 0 && <li className="search-empty">검색 결과가 없어요.</li>}
          </ul>
        </div>
      </main>
    </Layout>
  )
}
