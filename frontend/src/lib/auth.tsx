import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, getToken, setToken } from './api'
import type { User } from './types'

// 로그인 상태는 localStorage에 저장된 토큰·사용자 정보로 바로 그린다.
// 서버 확인(/auth/me)은 뒤에서 하고, 토큰이 만료됐을 때만 조용히 로그아웃한다.
// → 서버가 잠들어 있어도 첫 화면이 기다리지 않는다.

const USER_KEY = 'nd_user'

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw && getToken() ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

function saveUser(user: User | null) {
  try {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
  } catch {
    // 무시
  }
}

interface AuthValue {
  user: User | null
  login: (token: string, user?: User) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(loadUser)

  const logout = useCallback(() => {
    setToken(null)
    saveUser(null)
    setUser(null)
  }, [])

  const refresh = useCallback(async () => {
    if (!getToken()) return
    try {
      const { user: me } = await api<{ user: User }>('/api/v1/auth/me')
      saveUser(me)
      setUser(me)
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) logout()
    }
  }, [logout])

  const login = useCallback(async (token: string, me?: User) => {
    setToken(token)
    if (me) {
      saveUser(me)
      setUser(me)
    } else {
      await refresh()
    }
  }, [refresh])

  useEffect(() => {
    refresh()
  }, [refresh])

  return <AuthContext.Provider value={{ user, login, logout, refresh }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('AuthProvider 안에서만 쓸 수 있어요')
  return ctx
}
