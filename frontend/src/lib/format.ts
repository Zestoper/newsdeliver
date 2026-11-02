// 서버 DB 시각은 UTC인데 시간대 표시 없이("2026-11-02T11:40:00") 내려온다.
// 그대로 new Date() 하면 브라우저가 한국 시각으로 읽어서 9시간 일찍 보이므로 UTC로 읽게 Z를 붙인다.
const NAIVE_DATETIME = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/

function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const d = new Date(NAIVE_DATETIME.test(value) ? `${value.replace(' ', 'T')}Z` : value)
  return Number.isNaN(d.getTime()) ? null : d
}

const pad = (n: number) => String(n).padStart(2, '0')

// 2026.10.12
export function fmtDate(value: string | null | undefined): string {
  const d = toDate(value)
  return d ? `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}` : (value ?? '')
}

// 10.12 14:30
export function fmtShort(value: string | null | undefined): string {
  const d = toDate(value)
  return d ? `${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}` : ''
}

// 2026년 10월 12일 14:30
export function fmtLong(value: string | null | undefined): string {
  const d = toDate(value)
  return d ? `${d.getFullYear()}년 ${pad(d.getMonth() + 1)}월 ${pad(d.getDate())}일 ${pad(d.getHours())}:${pad(d.getMinutes())}` : ''
}

// 기사 대표 이미지로 쓸 수 있는 주소인지 (기존 템플릿과 같은 기준)
export function usableImage(url: string | null | undefined): url is string {
  return !!url && url.startsWith('http') && !url.endsWith('.html') && !url.endsWith('.nhn')
}

export function excerpt(text: string | null | undefined, len = 80): string {
  const t = (text ?? '').replace(/\s+/g, ' ').trim()
  return t.length > len ? `${t.slice(0, len)}...` : t
}
