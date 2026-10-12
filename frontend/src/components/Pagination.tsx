import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight } from 'lucide-react'

// 기존 템플릿과 같은 규칙: 현재 페이지 ±2, 처음·마지막, 그 밖은 …
export default function Pagination({ page, totalPages, href }: { page: number; totalPages: number; href: (p: number) => string }) {
  if (totalPages <= 1) return null
  const items: (number | 'gap')[] = []
  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || (p >= page - 2 && p <= page + 2)) items.push(p)
    else if (p === page - 3 || p === page + 3) items.push('gap')
  }
  return (
    <div className="pagination">
      {page > 1
        ? <Link to={href(page - 1)} className="page-btn"><ArrowLeft size="1em" /> 이전</Link>
        : <span className="page-btn disabled"><ArrowLeft size="1em" /> 이전</span>}
      {items.map((p, i) => p === 'gap'
        ? <span key={`g${i}`} className="page-btn ellipsis">…</span>
        : p === page
          ? <span key={p} className="page-btn active">{p}</span>
          : <Link key={p} to={href(p)} className="page-btn">{p}</Link>)}
      {page < totalPages
        ? <Link to={href(page + 1)} className="page-btn">다음 <ArrowRight size="1em" /></Link>
        : <span className="page-btn disabled">다음 <ArrowRight size="1em" /></span>}
    </div>
  )
}
