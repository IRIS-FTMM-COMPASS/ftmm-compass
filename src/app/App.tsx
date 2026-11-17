import {
  AlertCircle,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  LayoutDashboard,
  LogOut,
  Map,
  MessageSquare,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  User,
  Users,
  X,
} from "lucide-react"
import {
  useState,
  useMemo,
  useEffect,
  useCallback,
  type FormEvent,
} from "react"
import { cn } from "@/shared/utils"
import type { Course } from "@/shared/domain/models"

import Dashboard from "@/features/dashboard/DashboardPage"
import CourseFinder from "@/features/course-finder/CourseFinderPage"
import DegreePlanner from "@/features/degree-planner/DegreePlannerPage"
import Chatbot from "@/features/chatbot/ChatbotPage"
import type { DegreePlanPayload } from "@/shared/domain/plan"
import {
  INITIAL_CHAT_MESSAGES,
  INITIAL_STUDENT_PROFILE,
  type ChatMessage,
  type StudentProfileState,
} from "@/features/chatbot/chatService"
import Profile from "@/features/profile/ProfilePage"
import Login from "@/features/auth/LoginPage"
import {
  authService,
  authErrorMessage,
  copyToClipboard,
  downloadTextFile,
  fieldError,
  type AdminAccount,
} from "@/features/auth/authService"
import ErrorBoundary from "@/app/components/ErrorBoundary"
import { SessionProvider, useSession } from "@/features/auth/session"
import { CatalogProvider, useCatalog } from "@/features/catalog/catalog"
import { PollingProvider } from "@/features/polling/polling"
import {
  PlannerProvider,
  usePlanner,
} from "@/features/degree-planner/state/planner"

import BrandLogo from "@/shared/ui/BrandLogo"
import AnimatedMenuToggle from "@/app/components/AnimatedMenuToggle"
import NotificationDropdown from "@/app/components/NotificationDropdown"
import {
  AcademicPeriodProvider,
  useAcademicPeriod,
} from "@/shared/academic-period/academic"

type Page = "dashboard" | "course-finder" | "degree-planner" | "chatbot" | "profile" | "admin-accounts"

const ADMIN_ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  lecturer: "Dosen",
  student: "Mahasiswa",
}

const ADMIN_INPUT_CLASS =
  "w-full min-h-11 rounded-xl border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted focus:border-gold focus:ring-1 focus:ring-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 transition-all disabled:opacity-70"

const ADMIN_ACTION_CLASS =
  "min-h-11 inline-flex items-center justify-center gap-2 rounded-xl px-4 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"

function AdminFieldMessage({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p className="mt-1 text-xs text-orange" role="alert">
      {message}
    </p>
  )
}

function AdminAccounts() {
  const [items, setItems] = useState<AdminAccount[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const pageSize = 20
  const [searchInput, setSearchInput] = useState("")
  const [search, setSearch] = useState("")
  const [role, setRole] = useState("all")
  const [status, setStatus] = useState("all")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState({
    email: "",
    full_name: "",
    role: "lecturer",
    password: "",
  })
  const [createError, setCreateError] = useState<unknown>(null)
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(
    null,
  )
  const [copyMessage, setCopyMessage] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const reload = useCallback(() => setReloadToken((value) => value + 1), [])

  useEffect(() => {
    let isCurrent = true
    setIsLoading(true)
    setError(null)
    authService
      .listAccounts({ search, role, status, page, page_size: pageSize })
      .then((result) => {
        if (!isCurrent) return
        setItems(result.items)
        setTotal(result.total)
        setPages(result.pages)
      })
      .catch((err: unknown) => {
        if (isCurrent) setError(err)
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false)
      })
    return () => {
      isCurrent = false
    }
  }, [search, role, status, page, reloadToken])

  const applyFilters = (e: FormEvent) => {
    e.preventDefault()
    setPage(1)
    setSearch(searchInput.trim())
    reload()
  }

  const applySelection = (nextRole: string, nextStatus: string) => {
    setPage(1)
    setRole(nextRole)
    setStatus(nextStatus)
    reload()
  }

  const toggleStatus = async (account: AdminAccount) => {
    setBusyId(account.user_id)
    setError(null)
    setSuccess(null)
    try {
      await authService.setAccountStatus(account.user_id, !account.is_active)
      setSuccess(
        account.is_active
          ? "Akun berhasil dinonaktifkan."
          : "Akun berhasil diaktifkan.",
      )
      reload()
    } catch (err: unknown) {
      setError(err)
    } finally {
      setBusyId(null)
    }
  }

  const createStaff = async (e: FormEvent) => {
    e.preventDefault()
    setCreateError(null)
    try {
      const result = await authService.createStaff({
        email: createForm.email.trim(),
        full_name: createForm.full_name.trim(),
        role: createForm.role === "admin" ? "admin" : "lecturer",
        ...(createForm.password.trim()
          ? { password: createForm.password }
          : {}),
      })
      setCreateForm({
        email: "",
        full_name: "",
        role: "lecturer",
        password: "",
      })
      setIsCreateOpen(false)
      if (result.temporary_password) {
        setTemporaryPassword(result.temporary_password)
        setCopyMessage(null)
      } else {
        setSuccess("Akun staf berhasil dibuat.")
      }
      setPage(1)
      reload()
    } catch (err: unknown) {
      setCreateError(err)
    }
  }

  const resetPassword = async (account: AdminAccount) => {
    setBusyId(account.user_id)
    setError(null)
    setSuccess(null)
    try {
      const result = await authService.resetAccountPassword(account.user_id)
      if (result.temporary_password) {
        setTemporaryPassword(result.temporary_password)
        setCopyMessage(null)
      }
    } catch (err: unknown) {
      setError(err)
    } finally {
      setBusyId(null)
    }
  }

  const copyTemporaryPassword = async () => {
    if (!temporaryPassword) return
    const copied = await copyToClipboard(temporaryPassword)
    setCopyMessage(
      copied
        ? "Kata sandi sementara berhasil disalin."
        : "Kata sandi tidak dapat disalin otomatis. Silakan salin secara manual.",
    )
  }

  const downloadTemporaryPassword = () => {
    if (!temporaryPassword) return
    downloadTextFile(
      "kata-sandi-sementara-ftmm-compass.txt",
      `Kata Sandi Sementara FTMM Compass\n\nKata sandi: ${temporaryPassword}\n\nGunakan kata sandi ini sekali dan segera ganti setelah masuk.\n`,
    )
  }

  const generalError = error
    ? authErrorMessage(error, "Daftar akun tidak dapat dimuat.")
    : null
  const createGeneralError =
    createError &&
    !fieldError(createError, "email") &&
    !fieldError(createError, "full_name") &&
    !fieldError(createError, "role") &&
    !fieldError(createError, "password")
      ? authErrorMessage(createError, "Akun staf gagal dibuat.")
      : null

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-border bg-surface p-5 md:p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-navy/10 text-navy flex items-center justify-center flex-shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-heading font-bold text-xl text-navy">
                Manajemen Akun
              </h2>
              <p className="text-xs text-muted mt-1">
                Kelola akun, status, dan kata sandi pengguna FTMM Compass.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setCreateError(null)
              setIsCreateOpen(true)
            }}
            className={cn(
              ADMIN_ACTION_CLASS,
              "bg-navy text-white hover:bg-navy-light",
            )}
          >
            <Plus className="w-4 h-4" /> Buat akun staf
          </button>
        </div>

        <form
          onSubmit={applyFilters}
          className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end"
        >
          <div className="space-y-1.5">
            <label
              htmlFor="account-search"
              className="text-xs font-medium text-foreground"
            >
              Pencarian
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input
                id="account-search"
                type="search"
                placeholder="Cari nama atau email"
                className={cn(ADMIN_INPUT_CLASS, "pl-9")}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor="account-role"
              className="text-xs font-medium text-foreground"
            >
              Peran
            </label>
            <select
              id="account-role"
              className={ADMIN_INPUT_CLASS}
              value={role}
              onChange={(e) => applySelection(e.target.value, status)}
            >
              <option value="all">Semua peran</option>
              <option value="student">Mahasiswa</option>
              <option value="lecturer">Dosen</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label
              htmlFor="account-status"
              className="text-xs font-medium text-foreground"
            >
              Status
            </label>
            <select
              id="account-status"
              className={ADMIN_INPUT_CLASS}
              value={status}
              onChange={(e) => applySelection(role, e.target.value)}
            >
              <option value="all">Semua status</option>
              <option value="active">Aktif</option>
              <option value="inactive">Nonaktif</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className={cn(
                ADMIN_ACTION_CLASS,
                "bg-navy text-white hover:bg-navy-light",
              )}
            >
              Terapkan
            </button>
            <button
              type="button"
              onClick={() => {
                setSearchInput("")
                setSearch("")
                applySelection("all", "all")
              }}
              className={cn(
                ADMIN_ACTION_CLASS,
                "border border-border bg-background text-foreground hover:bg-secondary",
              )}
            >
              Atur ulang
            </button>
          </div>
        </form>

        {generalError && (
          <div
            className="mt-4 flex items-start gap-2 rounded-xl border border-orange/30 bg-orange/10 p-3 text-sm text-orange"
            role="alert"
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{generalError}</span>
          </div>
        )}
        {success && (
          <div
            className="mt-4 flex items-start gap-2 rounded-xl border border-gold/30 bg-gold/10 p-3 text-sm text-navy"
            role="status"
          >
            <Check className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{success}</span>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-border bg-surface shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-secondary text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Nama</th>
                <th className="px-4 py-3 font-semibold">Email</th>
                <th className="px-4 py-3 font-semibold">Peran</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">NIM</th>
                <th className="px-4 py-3 font-semibold">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-muted">
                    Memuat daftar akun
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-muted">
                    Tidak ada akun yang cocok dengan filter.
                  </td>
                </tr>
              ) : (
                items.map((account) => (
                  <tr key={account.user_id} className="hover:bg-secondary/60">
                    <td className="px-4 py-3 font-medium text-foreground">
                      {account.full_name || "Tidak tersedia"}
                    </td>
                    <td className="px-4 py-3 text-muted">{account.email}</td>
                    <td className="px-4 py-3 text-muted">
                      {ADMIN_ROLE_LABELS[account.role] ?? account.role}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium",
                          account.is_active
                            ? "bg-teal/15 text-navy"
                            : "bg-orange/10 text-orange",
                        )}
                      >
                        {account.is_active ? "Aktif" : "Nonaktif"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted font-mono">
                      {account.student_number ?? "Tidak tersedia"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          disabled={busyId === account.user_id}
                          onClick={() => void toggleStatus(account)}
                          className={cn(
                            ADMIN_ACTION_CLASS,
                            "border border-border bg-background text-navy hover:bg-secondary px-3",
                          )}
                        >
                          {account.is_active ? "Nonaktifkan" : "Aktifkan"}
                        </button>
                        <button
                          type="button"
                          disabled={busyId === account.user_id}
                          onClick={() => void resetPassword(account)}
                          className={cn(
                            ADMIN_ACTION_CLASS,
                            "border border-orange/30 bg-orange/10 text-orange hover:bg-orange/20 px-3",
                          )}
                        >
                          <RotateCcw className="w-4 h-4" /> Reset sandi
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3">
          <p className="text-xs text-muted">
            Menampilkan {items.length} dari {total} akun
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Halaman sebelumnya"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              className={cn(
                ADMIN_ACTION_CLASS,
                "min-w-11 border border-border bg-background text-navy hover:bg-secondary px-2",
              )}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-foreground">
              Halaman {page} dari {Math.max(1, pages)}
            </span>
            <button
              type="button"
              aria-label="Halaman berikutnya"
              disabled={page >= pages || isLoading}
              onClick={() => setPage((value) => Math.min(pages, value + 1))}
              className={cn(
                ADMIN_ACTION_CLASS,
                "min-w-11 border border-border bg-background text-navy hover:bg-secondary px-2",
              )}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {isCreateOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-account-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setIsCreateOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 space-y-4 animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <h3
                id="create-account-title"
                className="font-heading font-bold text-lg text-navy"
              >
                Buat Akun Staf
              </h3>
              <button
                type="button"
                onClick={() => setIsCreateOpen(false)}
                aria-label="Tutup"
                className="min-h-11 min-w-11 rounded-lg flex items-center justify-center text-muted hover:text-navy hover:bg-secondary cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {createGeneralError && (
              <div
                className="flex items-start gap-2 rounded-xl border border-orange/30 bg-orange/10 p-3 text-sm text-orange"
                role="alert"
              >
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{createGeneralError}</span>
              </div>
            )}
            <form onSubmit={createStaff} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="staff-name"
                  className="text-sm font-medium text-foreground"
                >
                  Nama Lengkap
                </label>
                <input
                  id="staff-name"
                  type="text"
                  required
                  className={ADMIN_INPUT_CLASS}
                  value={createForm.full_name}
                  onChange={(e) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      full_name: e.target.value,
                    }))
                  }
                  aria-invalid={Boolean(fieldError(createError, "full_name"))}
                  disabled={isLoading}
                />
                <AdminFieldMessage
                  message={fieldError(createError, "full_name")}
                />
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="staff-email"
                  className="text-sm font-medium text-foreground"
                >
                  Email
                </label>
                <input
                  id="staff-email"
                  type="email"
                  required
                  className={ADMIN_INPUT_CLASS}
                  value={createForm.email}
                  onChange={(e) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      email: e.target.value,
                    }))
                  }
                  aria-invalid={Boolean(fieldError(createError, "email"))}
                  disabled={isLoading}
                />
                <AdminFieldMessage message={fieldError(createError, "email")} />
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="staff-role"
                  className="text-sm font-medium text-foreground"
                >
                  Peran
                </label>
                <select
                  id="staff-role"
                  className={ADMIN_INPUT_CLASS}
                  value={createForm.role}
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, role: e.target.value }))
                  }
                  disabled={isLoading}
                >
                  <option value="lecturer">Dosen</option>
                  <option value="admin">Administrator</option>
                </select>
                <AdminFieldMessage message={fieldError(createError, "role")} />
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="staff-password"
                  className="text-sm font-medium text-foreground"
                >
                  Kata Sandi
                </label>
                <input
                  id="staff-password"
                  type="password"
                  className={ADMIN_INPUT_CLASS}
                  placeholder="Kosongkan untuk kata sandi sementara"
                  value={createForm.password}
                  onChange={(e) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      password: e.target.value,
                    }))
                  }
                  aria-invalid={Boolean(fieldError(createError, "password"))}
                  disabled={isLoading}
                />
                <AdminFieldMessage
                  message={fieldError(createError, "password")}
                />
              </div>
              <div className="grid grid-cols-2 gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className={cn(
                    ADMIN_ACTION_CLASS,
                    "border border-border bg-background text-foreground hover:bg-secondary",
                  )}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className={cn(
                    ADMIN_ACTION_CLASS,
                    "bg-navy text-white hover:bg-navy-light",
                  )}
                >
                  Buat akun
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {temporaryPassword && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="temporary-password-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setTemporaryPassword(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 space-y-4 animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-center">
              <div className="w-12 h-12 rounded-full bg-gold/10 text-gold flex items-center justify-center border border-gold/30">
                <ShieldCheck className="w-6 h-6" />
              </div>
            </div>
            <div className="text-center space-y-1">
              <h3
                id="temporary-password-title"
                className="font-heading font-bold text-lg text-navy"
              >
                Kata Sandi Sementara
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                Kata sandi ini hanya ditampilkan sekali. Sesi akun terkait telah
                dicabut dan kata sandi harus segera diganti.
              </p>
            </div>
            <div className="rounded-xl border border-gold/40 bg-background p-4">
              <code className="block font-mono text-lg text-navy break-all select-all">
                {temporaryPassword}
              </code>
            </div>
            {copyMessage && (
              <p className="text-xs text-navy text-center" role="status">
                {copyMessage}
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => void copyTemporaryPassword()}
                className={cn(
                  ADMIN_ACTION_CLASS,
                  "border border-border bg-surface text-navy hover:bg-secondary",
                )}
              >
                <Copy className="w-4 h-4" /> Salin
              </button>
              <button
                type="button"
                onClick={downloadTemporaryPassword}
                className={cn(
                  ADMIN_ACTION_CLASS,
                  "border border-border bg-surface text-navy hover:bg-secondary",
                )}
              >
                <Download className="w-4 h-4" /> Unduh
              </button>
            </div>
            <button
              type="button"
              onClick={() => {
                setTemporaryPassword(null)
                setCopyMessage(null)
              }}
              className={cn(
                ADMIN_ACTION_CLASS,
                "w-full bg-navy text-white hover:bg-navy-light",
              )}
            >
              Selesai
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  return (
    <SessionProvider>
      <AcademicPeriodProvider>
        <CatalogProvider>
          <PollingProvider>
            <PlannerProvider>
              <AppShell />
            </PlannerProvider>
          </PollingProvider>
        </CatalogProvider>
      </AcademicPeriodProvider>
    </SessionProvider>
  )
}

function AppShell() {
  const { user, isLoggedIn, login, logout, canAccess } = useSession()
  const { period } = useAcademicPeriod()
  const { error: catalogError, reload: reloadCatalog } = useCatalog()
  const planner = usePlanner()
  const [activePage, setActivePage] = useState<Page>("dashboard")
  const [isSidebarOpen, setIsSidebarOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth >= 768,
  )
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false)
  const [plannerInitialTab, setPlannerInitialTab] =
    useState<"roadmap" | "timetable">("roadmap")
  const [finderInitialCourse, setFinderInitialCourse] = useState<Course | null>(
    null,
  )
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(
    INITIAL_CHAT_MESSAGES,
  )
  const [chatProfile, setChatProfile] = useState<StudentProfileState>(
    INITIAL_STUDENT_PROFILE,
  )
  const [chatAppliedPlanId, setChatAppliedPlanId] = useState<string | null>(
    null,
  )
  useEffect(() => {
    if (!canAccess(activePage)) setActivePage("dashboard")
  }, [activePage, canAccess])
  useEffect(() => {
    if (isLoggedIn) return
    setChatMessages(INITIAL_CHAT_MESSAGES)
    setChatProfile(INITIAL_STUDENT_PROFILE)
    setChatAppliedPlanId(null)
    setIsLogoutModalOpen(false)
    setActivePage("dashboard")
  }, [isLoggedIn])
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return
      if (isLogoutModalOpen) setIsLogoutModalOpen(false)
      else if (isSidebarOpen) setIsSidebarOpen(false)
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isLogoutModalOpen, isSidebarOpen])

  const handleNavigate = (
    page: string,
    options?: {
      tab?: "roadmap" | "timetable"
      course?: Course
    },
  ) => {
    setPlannerInitialTab(options?.tab || "roadmap")
    setFinderInitialCourse(options?.course || null)
    setActivePage(page as Page)
  }

  const handleApplyPlanFromChatbot = (payload: DegreePlanPayload) => {
    planner.applyPlan(payload)
    handleNavigate("degree-planner")
  }

  const handleLogout = () => {
    logout()
    setIsLogoutModalOpen(false)
    setChatMessages(INITIAL_CHAT_MESSAGES)
    setChatProfile(INITIAL_STUDENT_PROFILE)
    setChatAppliedPlanId(null)
    setActivePage("dashboard")
  }

  const addedCourseIds = new Set(
    planner.pendingCourses.map((course) => course.id),
  )

  const navItems = useMemo(() => {
    const role = user?.role || "student"
    if (role === "lecturer") {
      return [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "course-finder", label: "Course Finder", icon: Search },
      ] as const
    }
    if (role === "admin") {
      return [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "course-finder", label: "Course Management", icon: BookOpen },
        { id: "admin-accounts", label: "Manajemen Akun", icon: Users },
      ] as const
    }
    return [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { id: "course-finder", label: "Course Finder", icon: Search },
      { id: "degree-planner", label: "Degree Planner", icon: Map },
      { id: "chatbot", label: "Compass AI", icon: MessageSquare },
    ] as const
  }, [user?.role])

  if (!isLoggedIn) {
    return (
      <Login
        onLogin={(next, expiresInSeconds) => {
          login(next, expiresInSeconds)
          setActivePage("dashboard")
        }}
      />
    )
  }

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden font-sans text-foreground">
      <aside
        inert={!isSidebarOpen}
        aria-hidden={!isSidebarOpen}
        className={cn(
          "bg-navy text-white flex flex-col flex-shrink-0 shadow-xl z-20 transition-all duration-300 ease-in-out absolute md:relative h-full overflow-hidden",
          isSidebarOpen
            ? "w-64 translate-x-0 opacity-100"
            : "w-0 -translate-x-full md:translate-x-0 opacity-0 pointer-events-none",
        )}
      >
        <div className="flex flex-col h-full w-64 min-w-[16rem]">
          <button
            onClick={() => setIsSidebarOpen(false)}
            aria-label="Tutup menu"
            className="md:hidden absolute top-4 right-4 min-h-11 min-w-11 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors z-10 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="p-5 pb-3">
            <BrandLogo variant="sidebar" />
          </div>

          <nav className="flex-1 px-4 py-6 space-y-2 border-t border-navy-light/50">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = activePage === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    handleNavigate(item.id)
                    if (window.innerWidth < 768) setIsSidebarOpen(false)
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-150 group text-left",
                    isActive
                      ? "bg-navy-light border-l-4 border-gold text-white"
                      : "text-muted hover:text-white hover:bg-navy-light/50 border-l-4 border-transparent",
                  )}
                >
                  <Icon
                    className={cn(
                      "w-5 h-5 flex-shrink-0",
                      isActive
                        ? "text-gold"
                        : "text-teal-light group-hover:text-teal-light",
                    )}
                  />
                  <span className="font-medium whitespace-nowrap">
                    {item.label}
                  </span>
                </button>
              )
            })}
          </nav>

          <div className="p-4 border-t border-navy-light/50">
            <div
              className={cn(
                "flex items-center gap-2 p-1.5 rounded-xl transition-all",
                activePage === "profile"
                  ? "bg-navy-light border border-gold/40 text-white shadow-xs"
                  : "hover:bg-navy-light/50 text-teal-light hover:text-white border border-transparent",
              )}
            >
              <button
                type="button"
                onClick={() => {
                  handleNavigate("profile")
                  if (window.innerWidth < 768) setIsSidebarOpen(false)
                }}
                className="flex items-center gap-3 flex-1 min-w-0 text-left cursor-pointer group p-1 rounded-lg"
                title="Buka Halaman Profil Pengguna"
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 font-heading font-bold text-xs transition-transform group-hover:scale-105",
                    activePage === "profile"
                      ? "bg-gold text-navy"
                      : "bg-teal text-navy-dark",
                  )}
                >
                  {user?.full_name ? (
                    user.full_name
                      .split(" ")
                      .filter(Boolean)
                      .slice(0, 2)
                      .map((n) => n[0])
                      .join("")
                      .toUpperCase()
                  ) : (
                    <User className="w-4 h-4" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate text-white group-hover:text-gold transition-colors">
                    {user?.full_name || "Mahasiswa FTMM"}
                  </p>
                  <p className="text-xs text-muted font-mono truncate">
                    {user?.student_profile?.student_number ||
                      user?.email ||
                      user?.role}
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setIsLogoutModalOpen(true)}
                title="Keluar / Logout dari Sesi"
                aria-label="Logout"
                className="min-h-11 min-w-11 rounded-lg flex items-center justify-center transition-colors text-muted hover:text-orange hover:bg-orange/15 flex-shrink-0 cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {isSidebarOpen && (
          <div
            className="absolute inset-0 bg-black/50 z-10 md:hidden backdrop-blur-sm"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        <header className="h-16 bg-surface border-b border-border flex items-center justify-between px-4 md:px-8 flex-shrink-0 relative z-30">
          <div className="flex items-center gap-3">
            <AnimatedMenuToggle
              isOpen={isSidebarOpen}
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            />
            <h2 className="font-heading text-xl md:text-2xl font-bold text-navy capitalize truncate">
              {activePage === "admin-accounts"
                ? "Manajemen Akun"
                : activePage === "chatbot"
                  ? "Compass AI"
                  : activePage === "profile"
                    ? "Profil Pengguna"
                    : activePage === "course-finder" && user?.role === "admin"
                      ? "Course Management"
                      : activePage.replace("-", " ")}
            </h2>
          </div>
          <div className="flex items-center gap-2 md:gap-4">
            <NotificationDropdown currentUser={user} />
            <div className="text-sm text-right hidden sm:block">
              <p className="font-medium text-navy">
                {period?.label ?? "Periode akademik"}
              </p>
              <p className="text-xs text-muted font-mono">
                {period?.week_label ?? ""}
              </p>
            </div>
          </div>
        </header>

        <div
          className={cn(
            "flex-1 overflow-auto relative",
            activePage === "degree-planner"
              ? "p-4 md:px-6 md:py-4"
              : "p-4 md:p-8",
          )}
        >
          {catalogError && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-navy">
              <span>{catalogError}</span>
              <button
                type="button"
                onClick={() => void reloadCatalog()}
                className="min-h-11 rounded-lg border border-orange/40 px-3 font-semibold text-orange transition-colors hover:bg-orange/10 cursor-pointer"
              >
                Coba lagi
              </button>
            </div>
          )}
          <div
            className={cn(
              "mx-auto h-full",
              activePage === "degree-planner"
                ? "w-full max-w-none"
                : "max-w-7xl",
            )}
          >
            <ErrorBoundary key={activePage}>
              {activePage === "dashboard" && (
                <Dashboard onNavigate={handleNavigate} />
              )}
              {activePage === "course-finder" && (
                <CourseFinder
                  onAddToPlanner={planner.addPendingCourse}
                  addedCourseIds={addedCourseIds}
                  initialCourse={finderInitialCourse}
                  onClearInitialCourse={() => setFinderInitialCourse(null)}
                />
              )}
              {activePage === "degree-planner" && (
                <DegreePlanner
                  onNavigate={handleNavigate}
                  initialTab={plannerInitialTab}
                />
              )}
              {activePage === "chatbot" && (
                <Chatbot
                  messages={chatMessages}
                  onMessagesChange={setChatMessages}
                  profile={chatProfile}
                  onProfileChange={setChatProfile}
                  appliedPlanId={chatAppliedPlanId}
                  onAppliedPlanIdChange={setChatAppliedPlanId}
                  onResetChat={() => {
                    setChatMessages(INITIAL_CHAT_MESSAGES)
                    setChatProfile(INITIAL_STUDENT_PROFILE)
                    setChatAppliedPlanId(null)
                  }}
                  onApplyPlan={handleApplyPlanFromChatbot}
                />
              )}
              {activePage === "profile" && (
                <Profile
                  onNavigate={handleNavigate}
                  onRequestLogout={() => setIsLogoutModalOpen(true)}
                />
              )}
              {activePage === "admin-accounts" && user?.role === "admin" && (
                <AdminAccounts />
              )}
            </ErrorBoundary>
          </div>
        </div>
      </main>

      {isLogoutModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="logout-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setIsLogoutModalOpen(false)}
        >
          <div
            className="bg-surface rounded-2xl border border-border shadow-2xl max-w-sm w-full p-6 space-y-4 animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-12 h-12 rounded-full bg-orange/10 text-orange flex items-center justify-center mx-auto border border-orange/20">
              <LogOut className="w-6 h-6" />
            </div>

            <div className="text-center space-y-1">
              <h3
                id="logout-dialog-title"
                className="font-heading font-bold text-lg text-navy"
              >
                Konfirmasi Keluar
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                Apakah Anda yakin ingin mengakhiri sesi akademik di FTMM
                Compass? Anda dapat masuk kembali kapan saja dengan akun
                Cybercampus UNAIR.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsLogoutModalOpen(false)}
                className="w-full min-h-11 px-4 rounded-xl border border-border bg-background hover:bg-surface text-foreground font-medium text-xs transition-colors cursor-pointer"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="w-full min-h-11 px-4 rounded-xl bg-orange hover:bg-orange/90 text-white font-medium text-xs transition-colors cursor-pointer shadow-sm"
              >
                Ya, Keluar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
