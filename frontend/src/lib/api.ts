// 백엔드 API 호출 공통 함수 — 로그인 토큰을 Authorization 헤더에 붙여 보낸다

export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000'

const TOKEN_KEY = 'nd_token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // 저장소를 못 쓰는 환경이면 무시
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}


// Render 무료 서버는 잠들어 있으면 깨어나는 동안 연결이 끊기거나 502/503을 돌려준다.
// 조회(GET) 요청은 바로 실패로 보여주지 않고 서버가 깨어날 때까지(최대 약 90초) 다시 시도한다.
const WAKE_STATUSES = new Set([502, 503, 504])
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function fetchWaking(url: string, init: RequestInit, retry: boolean): Promise<Response> {
  const deadline = Date.now() + 90_000
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, init)
      if (!retry || !WAKE_STATUSES.has(res.status) || Date.now() > deadline) return res
    } catch (e) {
      if (!retry || Date.now() > deadline) throw e
    }
    await sleep(Math.min(1500 * (attempt + 1), 5000))
  }
}

type Body = Record<string, unknown> | FormData | undefined

export async function api<T = unknown>(path: string, options: { method?: string; body?: Body } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (options.body instanceof FormData) {
    body = options.body
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  const method = options.method ?? 'GET'
  const res = await fetchWaking(`${API_BASE}${path}`, { method, headers, body }, method === 'GET')
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : '요청을 처리하지 못했어요.'
    throw new ApiError(res.status, detail)
  }
  return data as T
}

// 폼 데이터로 보내야 하는 기존 엔드포인트(댓글·신고)용
export function form(fields: Record<string, string | number | null | undefined>): FormData {
  const fd = new FormData()
  for (const [k, v] of Object.entries(fields)) {
    if (v !== null && v !== undefined) fd.append(k, String(v))
  }
  return fd
}

// 서버에 저장된 파일 경로(/static/...)를 전체 주소로 바꾼다
export function mediaUrl(url: string): string {
  return url.startsWith('/') ? `${API_BASE}${url}` : url
}
