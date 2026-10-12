function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const d = new Date(value)
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
