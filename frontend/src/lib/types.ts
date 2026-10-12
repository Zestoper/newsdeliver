export interface User {
  id: string
  name: string
  email: string | null
  tel: string | null
  role: 'user' | 'admin' | 'press'
  birth: string | null
  oauth_provider: string | null
  press_approved: number | null
}

export interface NewsItem {
  id: number
  title: string
  image_url?: string | null
  content?: string | null
  source?: string | null
  created_at?: string | null
  view_count?: number | null
  category_name?: string | null
  like_count?: number
  comment_count?: number
}

export interface Category {
  id: number
  name: string
}

export interface NewsPage {
  news_items: NewsItem[]
  categories: Category[]
  selected_category: string
  page: number
  total_pages: number
}
