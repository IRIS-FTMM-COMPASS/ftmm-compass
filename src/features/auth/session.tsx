import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { API_BASE } from "@/shared/api/client"
import {
  authService,
  notifyUnauthorized,
  onTokenRenewed,
  onUnauthorized,
  type AuthUser,
} from "@/features/auth/authService"

const EXPIRY_KEY = "auth_expires_at"

const INACTIVE_ACCOUNT_MESSAGE = "Akun Anda dinonaktifkan oleh admin"

async function isInactiveAccountResponse(response: Response): Promise<boolean> {
  try {
    const payload: unknown = await response.clone().json()
    if (!payload || typeof payload !== "object") return false
    const body = payload as Record<string, unknown>
    const error =
      body.error && typeof body.error === "object"
        ? body.error as Record<string, unknown>
        : body
    return (
      error.code === "account_inactive" ||
      error.message === INACTIVE_ACCOUNT_MESSAGE
    )
  } catch {
    return false
  }
}

const STUDENT_ONLY_PAGES: Record<string, true> = {
  "degree-planner": true,
  chatbot: true,
}

const ADMIN_ONLY_PAGES: Record<string, true> = {
  "admin-accounts": true,
}

const LECTURER_ONLY_PAGES: Record<string, true> = {
  "pj-courses": true,
}

interface SessionContextValue {
  user: AuthUser | null
  isLoggedIn: boolean
  login: (user: AuthUser, expiresInSeconds?: number) => void
  logout: () => void
  setUser: (user: AuthUser) => void
  /** Satu-satunya aturan rute: halaman berdasarkan peran pengguna aktif. */
  canAccess: (page: string) => boolean
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<AuthUser | null>(() =>
    authService.getStoredUser(),
  )
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(() =>
    Boolean(authService.getStoredToken() && authService.getStoredUser()),
  )
  const expiryTimer = useRef<number | undefined>(undefined)
  const isLoggedInRef = useRef(isLoggedIn)
  isLoggedInRef.current = isLoggedIn

  const logout = useCallback(() => {
    clearTimeout(expiryTimer.current)
    expiryTimer.current = undefined
    try {
      window.localStorage.removeItem(EXPIRY_KEY)
    } catch {
      /* Penyimpanan lokal tidak tersedia. */
    }
    authService.logout()
    setUserState(null)
    setIsLoggedIn(false)
  }, [])

  const scheduleExpiry = useCallback(
    (expiresAt: number) => {
      clearTimeout(expiryTimer.current)
      const remaining = expiresAt - Date.now()
      if (remaining <= 0) {
        logout()
        return
      }
      const buffer = Math.min(30_000, remaining * 0.1)
      expiryTimer.current = window.setTimeout(
        logout,
        Math.max(0, remaining - buffer),
      )
    },
    [logout],
  )

  const login = useCallback(
    (next: AuthUser, expiresInSeconds?: number) => {
      setUserState(next)
      setIsLoggedIn(true)
      if (
        typeof expiresInSeconds === "number" &&
        Number.isFinite(expiresInSeconds) &&
        expiresInSeconds > 0
      ) {
        const expiresAt = Date.now() + expiresInSeconds * 1000
        try {
          window.localStorage.setItem(EXPIRY_KEY, String(expiresAt))
        } catch {
          /* Penyimpanan lokal tidak tersedia. */
        }
        scheduleExpiry(expiresAt)
      }
    },
    [scheduleExpiry],
  )

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(EXPIRY_KEY)
      if (!stored) return
      const expiresAt = Number(stored)
      if (Number.isFinite(expiresAt)) scheduleExpiry(expiresAt)
    } catch {
      /* Penyimpanan lokal tidak tersedia. */
    }
  }, [scheduleExpiry])

  useEffect(() => {
    const unsubscribeUnauthorized = onUnauthorized(logout)
    const unsubscribeRenewed = onTokenRenewed((expiresInSeconds) => {
      if (!Number.isFinite(expiresInSeconds) || expiresInSeconds <= 0) return
      const expiresAt = Date.now() + expiresInSeconds * 1000
      try {
        window.localStorage.setItem(EXPIRY_KEY, String(expiresAt))
      } catch {
        /* Penyimpanan lokal tidak tersedia. */
      }
      scheduleExpiry(expiresAt)
    })
    return () => {
      unsubscribeUnauthorized()
      unsubscribeRenewed()
    }
  }, [logout, scheduleExpiry])

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.fetch !== "function") {
      return
    }
    const originalFetch = window.fetch.bind(window)
    window.fetch = (input, init) =>
      originalFetch(input, init).then(async (response) => {
        if (response.status !== 401 || !isLoggedInRef.current) return response
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url
        if (!API_BASE || url.startsWith(API_BASE)) {
          const isInactive = await isInactiveAccountResponse(response)
          logout()
          if (isInactive) notifyUnauthorized()
        }
        return response
      })
    return () => {
      window.fetch = originalFetch
    }
  }, [logout])

  useEffect(
    () => () => {
      clearTimeout(expiryTimer.current)
    },
    [],
  )

  const canAccess = useCallback(
    (page: string) => {
      const role = user?.role ?? "student"
      if (ADMIN_ONLY_PAGES[page]) return role === "admin"
      if (STUDENT_ONLY_PAGES[page]) return role === "student"
      if (LECTURER_ONLY_PAGES[page]) return role === "lecturer"
      return true
    },
    [user?.role],
  )

  const value = useMemo(
    () => ({
      user,
      isLoggedIn,
      login,
      logout,
      setUser: setUserState,
      canAccess,
    }),
    [user, isLoggedIn, login, logout, canAccess],
  )

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  )
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error("useSession harus dipakai di dalam SessionProvider")
  }
  return context
}
