import { Link } from 'react-router-dom'
import Layout from '../components/Layout'

export default function NotFound() {
  return (
    <Layout title="페이지를 찾을 수 없어요">
      <main className="main-content" style={{ textAlign: 'center', padding: '96px 24px' }}>
        <p style={{ fontSize: 48, fontWeight: 900, color: '#D42B2B', marginBottom: 8 }}>404</p>
        <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 12 }}>페이지를 찾을 수 없어요</h2>
        <p style={{ color: '#6B7280', marginBottom: 28 }}>주소가 바뀌었거나 삭제된 페이지예요.</p>
        <Link to="/" className="header-btn" style={{ display: 'inline-block', padding: '10px 22px' }}>홈으로 가기</Link>
      </main>
    </Layout>
  )
}
