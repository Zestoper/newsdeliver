import { lazy, Suspense, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import Home from './pages/Home'

// 첫 화면(홈)만 바로 불러오고 나머지 페이지는 들어갈 때 불러온다
const About = lazy(() => import('./pages/About'))
const AgeNews = lazy(() => import('./pages/AgeNews'))
const AuthCallback = lazy(() => import('./pages/AuthCallback'))
const Contact = lazy(() => import('./pages/Contact'))
const Login = lazy(() => import('./pages/Login'))
const MyPage = lazy(() => import('./pages/MyPage'))
const NewsDetail = lazy(() => import('./pages/NewsDetail'))
const NewsList = lazy(() => import('./pages/NewsList'))
const NotFound = lazy(() => import('./pages/NotFound'))
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess'))
const Search = lazy(() => import('./pages/Search'))
const Signup = lazy(() => import('./pages/Signup'))
const Subscribe = lazy(() => import('./pages/Subscribe'))
const VerifyEmail = lazy(() => import('./pages/VerifyEmail'))

// 페이지를 옮기면 맨 위로 스크롤
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Suspense fallback={<div className="page-loading" />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/news" element={<NewsList />} />
          <Route path="/news/:id" element={<NewsDetail />} />
          <Route path="/global-news" element={<NewsList global />} />
          <Route path="/age-news/:group" element={<AgeNews />} />
          <Route path="/search" element={<Search />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/press/signup" element={<Signup press />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/mypage" element={<MyPage />} />
          <Route path="/subscribe" element={<Subscribe />} />
          <Route path="/subscribe/payment/success" element={<PaymentSuccess />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </>
  )
}
