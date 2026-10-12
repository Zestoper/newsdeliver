import { useEffect, type ReactNode } from 'react'
import Footer from './Footer'
import Header from './Header'

export default function Layout({ title, children, ticker, footer = true }: {
  title?: string
  children: ReactNode
  ticker?: { id: number; title: string }[]
  footer?: boolean
}) {
  useEffect(() => {
    document.title = title ? `${title} - News Delivery` : 'News Delivery'
  }, [title])
  return (
    <>
      <Header ticker={ticker} />
      {children}
      {footer && <Footer />}
    </>
  )
}
