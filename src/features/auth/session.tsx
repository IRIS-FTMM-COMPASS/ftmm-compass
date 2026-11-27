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
import {
  authService,
  onTokenRenewed,
  type AuthUser,
} from "@/features/auth/authService"
import { onUnauthorized } from "@/shared/api/session"

const EXPIRY_KEY = "auth_expires_at"

const STUDENT_ONLY_PAGES: Record<string, true> = {
  "degree-planner": true,
  chatbot: true,
}

const ADMIN_ONLY_PAGES: Record<string, true> = {
  "admin-accounts": true,
}

const LECTURER_ONLY_PAGES: Record<string, true> = {
  "pj-courses": true,
  preferences: true,
}

const SCHEDULING_PAGES: Record<string, true> = {
  scheduling: true,
}

const SCHEDULE_MANAGE_PAGES: Record<string, true> = {
  "teaching-team": true,
  "class-assignment": true,
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
    if (!authService.getStoredToken()) return
    let cancelled = false
    void authService
      .getMe()
      .then((next) => {
        if (!cancelled) setUserState(next)
      })
      .catch(() => {
        // 401 already clears the session through the shared transport.
      })
    return () => {
      cancelled = true
    }
  }, [])

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
      if (SCHEDULING_PAGES[page]) {
        return role === "admin" || role === "lecturer"
      }
      if (SCHEDULE_MANAGE_PAGES[page]) {
        return (
          role === "admin" ||
          (role === "lecturer" && user?.is_program_coordinator === true)
        )
      }
      return true
    },
    [user?.role, user?.is_program_coordinator],
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
