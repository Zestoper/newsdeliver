import { Link } from 'react-router-dom'
import { LogoMark } from './Logo'

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-logo" style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
          <LogoMark size={28} />
          <span><span style={{ color: '#ff6b6b' }}>News</span>Deliver</span>
        </div>
        <p className="footer-desc">카테고리 기반 뉴스 큐레이션 플랫폼</p>
        <div className="footer-links">
          <Link to="/about">회사 소개</Link>
          <Link to="/contact">문의하기</Link>
          <Link to="/subscribe">구독하기</Link>
        </div>
        <p className="footer-copy">&copy; 2026 News Delivery. All rights reserved.</p>
      </div>
    </footer>
  )
}
