import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

// GET 요청 하나를 불러오는 훅 — 경로가 바뀌면 다시 불러온다
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(!!path)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!path) return
    let alive = true
    setLoading(true)
    setError(null)
    api<T>(path)
      .then((d) => { if (alive) setData(d) })
      .catch((e: Error) => { if (alive) setError(e.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [path, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload, setData }
}
