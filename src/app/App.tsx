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
  Pencil,
  RotateCcw,
  Search,
  ShieldCheck,
  User,
  Users,
  X,
} from "lucide-react"
import {
  Fragment,
  useRef,
  useState,
  useMemo,
  useEffect,
  useCallback,
  type FormEvent,
  type MouseEvent,
} from "react"
import { cn } from "@/shared/utils"
import type { Course } from "@/shared/domain/models"

import Dashboard from "@/features/dashboard/DashboardPage"
import PjCoursesPage from "@/features/pj/PjCoursesPage"
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
  type AdminAcademicIdentityUpdate,
  type AdminAuthorityTrace,
} from "@/features/auth/authService"
import ConfirmDialog, {
  type ConfirmDialogValues,
} from "@/shared/ui/ConfirmDialog"
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

type Page = "dashboard" | "course-finder" | "pj-courses" | "degree-planner" | "chatbot" | "profile" | "admin-accounts"

const PAGES: Page[] = [
  "dashboard",
  "course-finder",
  "pj-courses",
  "degree-planner",
  "chatbot",
  "profile",
  "admin-accounts",
]

function isPage(value: string): value is Page {
  return PAGES.includes(value as Page)
}

function pathSegment(): string {
  return window.location.pathname.replace(/^\/+|\/+$/g, "")
}

function pageFromLocation(): Page {
  const path = pathSegment()
  return isPage(path) ? path : "dashboard"
}

function pageUrl(page: Page): string {
  return `/${page}`
}

function pageUrlWithContext(page: Page): string {
  return pageUrl(page) + window.location.search + window.location.hash
}

const ADMIN_ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  lecturer: "Dosen",
  student: "Mahasiswa",
}

const ADMIN_INPUT_CLASS =
  "w-full min-h-11 rounded-xl border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted focus:border-gold focus:ring-1 focus:ring-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 transition-all disabled:opacity-70"

const ADMIN_ACTION_CLASS =
  "min-h-11 inline-flex items-center justify-center gap-2 rounded-xl px-4 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"

const TRACE_PAGE_SIZE = 10

interface StatusAction {
  kind: "status"
  account: AdminAccount
  nextActive: boolean
}

interface ResetAction {
  kind: "reset"
  account: AdminAccount
}

interface AnonymizeAction {
  kind: "anonymize"
  account: AdminAccount
}

type AccountAction = StatusAction | ResetAction | AnonymizeAction

const TRACE_ACTION_LABELS: Record<string, string> = {
  status_change: "Perubahan status",
  password_reset: "Reset kata sandi",
  profile_correction: "Koreksi identitas akademik",
  anonymize: "Anonimisasi akun",
}

function traceSnapshotLabel(raw: string | null): string {
  if (!raw) return "Tidak tersedia"
  try {
    const parsed: unknown = JSON.parse(raw)
    if (
      parsed !== null &&
      typeof parsed === "object" &&
      !Array.isArray(parsed)
    ) {
      const snapshot = parsed as Record<string, unknown>
      const name =
        typeof snapshot.full_name === "string" ? snapshot.full_name : ""
      const identity =
        typeof snapshot.student_number === "string"
          ? snapshot.student_number
          : typeof snapshot.email === "string"
            ? snapshot.email
            : ""
      const label = [name, identity].filter(Boolean).join(", ")
      if (label) return label
    }
  } catch {
    // Snapshot bukan JSON: tampilkan teks aslinya.
  }
  return raw
}

function traceTimeLabel(value: string): string {
  if (!value) return "Tidak tersedia"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("id-ID", {
        dateStyle: "medium",
        timeStyle: "short",
      })
}

function accountStatusLabel(
  account: AdminAccount,
  anonymized: boolean,
): string {
  if (anonymized || account.anonymized_at) return "Akun dianonimisasi"
  return account.is_active ? "Aktif" : "Akun nonaktif"
}

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
  const [action, setAction] = useState<AccountAction | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [anonymizedIds, setAnonymizedIds] = useState<Set<string>>(
    () => new Set<string>(),
  )
  const [revalidatingIds, setRevalidatingIds] = useState<Set<string>>(
    () => new Set<string>(),
  )
  const [identityEditorId, setIdentityEditorId] = useState<string | null>(null)
  const [identityForm, setIdentityForm] = useState({
    study_program_id: "",
    admission_year: "",
    student_number: "",
    current_semester: "",
    reason: "",
  })
  const [identityBusy, setIdentityBusy] = useState(false)
  const [identityError, setIdentityError] = useState<unknown>(null)
  const identityLoadRef = useRef(0)
  const identitySubmittingRef = useRef(false)
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(
    null,
  )
  const [copyMessage, setCopyMessage] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const reload = useCallback(() => setReloadToken((value) => value + 1), [])

  const [traces, setTraces] = useState<AdminAuthorityTrace[]>([])
  const [traceTotal, setTraceTotal] = useState(0)
  const [tracePage, setTracePage] = useState(1)
  const [tracePages, setTracePages] = useState(1)
  const [traceLoading, setTraceLoading] = useState(false)
  const [traceError, setTraceError] = useState<unknown>(null)

  useEffect(() => {
    let isCurrent = true
    setTraceLoading(true)
    setTraceError(null)
    authService
      .listAuthorityTraces({ page: tracePage, page_size: TRACE_PAGE_SIZE })
      .then((result) => {
        if (!isCurrent) return
        setTraces(result.items)
        setTraceTotal(result.total)
        setTracePages(result.pages)
      })
      .catch((err: unknown) => {
        if (isCurrent) setTraceError(err)
      })
      .finally(() => {
        if (isCurrent) setTraceLoading(false)
      })
    return () => {
      isCurrent = false
    }
  }, [tracePage, reloadToken])

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

  const enrichActionAccount = useCallback(async (userId: string) => {
    try {
      const profile = await authService.getAcademicIdentity(userId)
      setAction((current) =>
        current && current.account.user_id === userId
          ? { ...current, account: { ...current.account, ...profile } }
          : current,
      )
    } catch {
      // Data dari daftar akun tetap dipakai bila endpoint profil belum tersedia.
    }
  }, [])

  const openAction = (next: AccountAction) => {
    setAction(next)
    setActionBusy(false)
    setActionError(null)
    setSuccess(null)
    void enrichActionAccount(next.account.user_id)
  }

  const confirmAction = async (values: ConfirmDialogValues) => {
    if (!action || actionBusy) return
    setActionBusy(true)
    setActionError(null)
    const currentAction = action
    try {
      if (currentAction.kind === "status") {
        await authService.setAccountStatus(
          currentAction.account.user_id,
          currentAction.nextActive,
          values.reason || undefined,
        )
        setSuccess(
          currentAction.nextActive
            ? "Akun berhasil diaktifkan kembali. Token lama tetap tidak berlaku."
            : "Akun nonaktif berhasil diterapkan. Login terblokir dan sesi aktif terputus.",
        )
      } else if (currentAction.kind === "reset") {
        const result = await authService.resetAccountPassword(
          currentAction.account.user_id,
          values.reason || undefined,
        )
        if (result.temporary_password) {
          setTemporaryPassword(result.temporary_password)
          setCopyMessage(null)
        }
        setSuccess("Kata sandi akun berhasil direset.")
      } else {
        await authService.anonymizeAccount(
          currentAction.account.user_id,
          currentAction.account.student_number ?? currentAction.account.email,
          values.reason,
        )
        setAnonymizedIds((previous) =>
          new Set(previous).add(currentAction.account.user_id),
        )
        setSuccess(
          "Akun dianonimisasi. Data pribadi dibersihkan dan riwayat akademik tetap tersimpan.",
        )
      }
      setAction(null)
      reload()
    } catch (err: unknown) {
      setActionError(authErrorMessage(err, "Aksi gagal. Silakan coba lagi."))
    } finally {
      setActionBusy(false)
    }
  }

  const openIdentityEditor = (account: AdminAccount) => {
    if (identityEditorId === account.user_id) {
      setIdentityEditorId(null)
      return
    }
    const loadId = identityLoadRef.current + 1
    identityLoadRef.current = loadId
    setIdentityError(null)
    setIdentityForm({
      study_program_id: account.study_program_id ?? "",
      admission_year: account.admission_year?.toString() ?? "",
      student_number: account.student_number ?? "",
      current_semester: account.current_semester?.toString() ?? "",
      reason: "",
    })
    setIdentityEditorId(account.user_id)
    void authService
      .getAcademicIdentity(account.user_id)
      .then((profile) => {
        if (identityLoadRef.current !== loadId) return
        setIdentityForm((previous) => ({
          study_program_id:
            previous.study_program_id || profile.study_program_id || "",
          admission_year:
            previous.admission_year || profile.admission_year?.toString() || "",
          student_number:
            previous.student_number || profile.student_number || "",
          current_semester:
            previous.current_semester ||
            profile.current_semester?.toString() ||
            "",
          reason: previous.reason,
        }))
      })
      .catch(() => {
        // Nilai dari daftar akun tetap dipakai bila prefill gagal dimuat.
      })
  }

  const saveIdentity = async (event: FormEvent, account: AdminAccount) => {
    event.preventDefault()
    if (identityBusy || identitySubmittingRef.current) return
    identitySubmittingRef.current = true
    setIdentityBusy(true)
    setIdentityError(null)
    const payload: AdminAcademicIdentityUpdate = {
      study_program_id: identityForm.study_program_id.trim(),
      admission_year: Number(identityForm.admission_year),
      student_number: identityForm.student_number.trim(),
      current_semester: Number(identityForm.current_semester),
      reason: identityForm.reason.trim(),
    }
    try {
      await authService.updateAcademicIdentity(account.user_id, payload)
      setIdentityEditorId(null)
      setSuccess(
        "Data identitas akademik terkunci berhasil dikoreksi. Mahasiswa perlu validasi ulang.",
      )
      setRevalidatingIds((previous) => new Set(previous).add(account.user_id))
      reload()
    } catch (err: unknown) {
      setIdentityError(err)
    } finally {
      identitySubmittingRef.current = false
      setIdentityBusy(false)
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

  const dialogConfirmationTarget =
    action?.kind === "anonymize"
      ? action.account.role === "student"
        ? action.account.student_number || action.account.email || ""
        : action.account.email
      : ""

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
                items.map((account) => {
                  const isAnonymized =
                    Boolean(account.anonymized_at) ||
                    anonymizedIds.has(account.user_id)
                  const isStudent = account.role === "student"
                  const isActionBusy =
                    actionBusy && action?.account.user_id === account.user_id
                  return (
                    <Fragment key={account.user_id}>
                      <tr className="hover:bg-secondary/60">
                        <td className="px-4 py-3 font-medium text-foreground">
                          {account.full_name || "Tidak tersedia"}
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {account.email}
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {ADMIN_ROLE_LABELS[account.role] ?? account.role}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium",
                              account.is_active && !isAnonymized
                                ? "bg-teal/15 text-navy"
                                : "bg-orange/10 text-orange",
                            )}
                          >
                            {accountStatusLabel(account, isAnonymized)}
                          </span>
                          {isStudent &&
                            (account.needs_revalidation ||
                              revalidatingIds.has(account.user_id)) && (
                              <span className="mt-1 block text-xs font-medium text-navy">
                                perlu validasi ulang
                              </span>
                            )}
                        </td>
                        <td className="px-4 py-3 text-muted font-mono">
                          {account.student_number ?? "Tidak tersedia"}
                          {isStudent && account.study_program && (
                            <span className="mt-1 block font-sans text-xs text-muted">
                              {account.study_program}
                              {account.admission_year
                                ? ` · ${account.admission_year}`
                                : ""}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              disabled={isAnonymized || isActionBusy}
                              onClick={() =>
                                openAction({
                                  kind: "status",
                                  account,
                                  nextActive: !account.is_active,
                                })
                              }
                              className={cn(
                                ADMIN_ACTION_CLASS,
                                "border border-border bg-background text-navy hover:bg-secondary px-3",
                              )}
                            >
                              {account.is_active ? "Nonaktifkan" : "Aktifkan"}
                            </button>
                            <button
                              type="button"
                              disabled={isActionBusy}
                              onClick={() =>
                                openAction({ kind: "reset", account })
                              }
                              className={cn(
                                ADMIN_ACTION_CLASS,
                                "border border-orange/30 bg-orange/10 text-orange hover:bg-orange/20 px-3",
                              )}
                            >
                              <RotateCcw className="w-4 h-4" /> Reset sandi
                            </button>
                            {isStudent && (
                              <button
                                type="button"
                                aria-expanded={
                                  identityEditorId === account.user_id
                                }
                                onClick={() => openIdentityEditor(account)}
                                className={cn(
                                  ADMIN_ACTION_CLASS,
                                  "border border-border bg-background text-navy hover:bg-secondary px-3",
                                )}
                              >
                                <Pencil className="w-4 h-4" /> Koreksi identitas
                              </button>
                            )}
                            <button
                              type="button"
                              disabled={isAnonymized || isActionBusy}
                              onClick={() =>
                                openAction({ kind: "anonymize", account })
                              }
                              className={cn(
                                ADMIN_ACTION_CLASS,
                                "border border-orange/30 bg-background text-orange hover:bg-orange/10 px-3",
                              )}
                            >
                              Anonimisasi
                            </button>
                          </div>
                        </td>
                      </tr>

                      {isStudent && identityEditorId === account.user_id && (
                        <tr className="bg-secondary/50">
                          <td colSpan={6} className="px-4 py-4">
                            <form
                              onSubmit={(event) =>
                                void saveIdentity(event, account)
                              }
                              className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4"
                            >
                              <div className="md:col-span-2 lg:col-span-4">
                                <h3 className="font-heading font-semibold text-navy">
                                  Data identitas akademik terkunci
                                </h3>
                                <p className="mt-1 text-xs text-muted">
                                  Hanya admin FTMM Compass yang dapat mengubah
                                  program studi, angkatan, NIM, dan semester
                                  aktif.
                                </p>
                              </div>
                              <div className="space-y-1.5">
                                <label
                                  htmlFor={`identity-program-${account.user_id}`}
                                  className="block text-xs font-semibold text-foreground"
                                >
                                  ID program studi *
                                </label>
                                <input
                                  id={`identity-program-${account.user_id}`}
                                  type="text"
                                  required
                                  value={identityForm.study_program_id}
                                  onChange={(event) =>
                                    setIdentityForm((previous) => ({
                                      ...previous,
                                      study_program_id: event.target.value,
                                    }))
                                  }
                                  placeholder="ID program studi"
                                  aria-invalid={Boolean(
                                    fieldError(
                                      identityError,
                                      "study_program_id",
                                    ),
                                  )}
                                  className={ADMIN_INPUT_CLASS}
                                />
                                <AdminFieldMessage
                                  message={fieldError(
                                    identityError,
                                    "study_program_id",
                                  )}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <label
                                  htmlFor={`identity-year-${account.user_id}`}
                                  className="block text-xs font-semibold text-foreground"
                                >
                                  Angkatan *
                                </label>
                                <input
                                  id={`identity-year-${account.user_id}`}
                                  type="number"
                                  min={1900}
                                  max={2100}
                                  required
                                  value={identityForm.admission_year}
                                  onChange={(event) =>
                                    setIdentityForm((previous) => ({
                                      ...previous,
                                      admission_year: event.target.value,
                                    }))
                                  }
                                  aria-invalid={Boolean(
                                    fieldError(identityError, "admission_year"),
                                  )}
                                  className={ADMIN_INPUT_CLASS}
                                />
                                <AdminFieldMessage
                                  message={fieldError(
                                    identityError,
                                    "admission_year",
                                  )}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <label
                                  htmlFor={`identity-nim-${account.user_id}`}
                                  className="block text-xs font-semibold text-foreground"
                                >
                                  NIM *
                                </label>
                                <input
                                  id={`identity-nim-${account.user_id}`}
                                  type="text"
                                  required
                                  value={identityForm.student_number}
                                  onChange={(event) =>
                                    setIdentityForm((previous) => ({
                                      ...previous,
                                      student_number: event.target.value,
                                    }))
                                  }
                                  placeholder="NIM mahasiswa"
                                  aria-invalid={Boolean(
                                    fieldError(identityError, "student_number"),
                                  )}
                                  className={ADMIN_INPUT_CLASS}
                                />
                                <AdminFieldMessage
                                  message={fieldError(
                                    identityError,
                                    "student_number",
                                  )}
                                />
                              </div>
                              <div className="space-y-1.5">
                                <label
                                  htmlFor={`identity-semester-${account.user_id}`}
                                  className="block text-xs font-semibold text-foreground"
                                >
                                  Semester aktif *
                                </label>
                                <input
                                  id={`identity-semester-${account.user_id}`}
                                  type="number"
                                  min={1}
                                  max={14}
                                  required
                                  value={identityForm.current_semester}
                                  onChange={(event) =>
                                    setIdentityForm((previous) => ({
                                      ...previous,
                                      current_semester: event.target.value,
                                    }))
                                  }
                                  aria-invalid={Boolean(
                                    fieldError(
                                      identityError,
                                      "current_semester",
                                    ),
                                  )}
                                  className={ADMIN_INPUT_CLASS}
                                />
                                <AdminFieldMessage
                                  message={fieldError(
                                    identityError,
                                    "current_semester",
                                  )}
                                />
                              </div>
                              <div className="space-y-1.5 md:col-span-2 lg:col-span-4">
                                <label
                                  htmlFor={`identity-reason-${account.user_id}`}
                                  className="block text-xs font-semibold text-foreground"
                                >
                                  Alasan koreksi *
                                </label>
                                <textarea
                                  id={`identity-reason-${account.user_id}`}
                                  rows={2}
                                  required
                                  value={identityForm.reason}
                                  onChange={(event) =>
                                    setIdentityForm((previous) => ({
                                      ...previous,
                                      reason: event.target.value,
                                    }))
                                  }
                                  placeholder="Alasan perubahan data identitas akademik"
                                  aria-invalid={Boolean(
                                    fieldError(identityError, "reason"),
                                  )}
                                  className={cn(ADMIN_INPUT_CLASS, "py-2")}
                                />
                                <AdminFieldMessage
                                  message={fieldError(identityError, "reason")}
                                />
                              </div>
                              {Boolean(identityError) && (
                                <div
                                  role="alert"
                                  className="flex items-start gap-2 rounded-xl border border-orange/30 bg-white p-3 text-sm text-orange md:col-span-2 lg:col-span-4"
                                >
                                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                  <span>
                                    {authErrorMessage(
                                      identityError,
                                      "Koreksi identitas akademik gagal. Periksa kembali nilai yang dimasukkan.",
                                    )}
                                  </span>
                                </div>
                              )}
                              <div className="flex flex-wrap gap-2 md:col-span-2 lg:col-span-4">
                                <button
                                  type="button"
                                  onClick={() => setIdentityEditorId(null)}
                                  disabled={identityBusy}
                                  className={cn(
                                    ADMIN_ACTION_CLASS,
                                    "border border-border bg-background text-foreground hover:bg-secondary",
                                  )}
                                >
                                  Batal
                                </button>
                                <button
                                  type="submit"
                                  disabled={identityBusy}
                                  className={cn(
                                    ADMIN_ACTION_CLASS,
                                    "bg-navy text-white hover:bg-navy-light",
                                  )}
                                >
                                  {identityBusy
                                    ? "Menyimpan..."
                                    : "Simpan koreksi"}
                                </button>
                              </div>
                            </form>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })
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

      <section className="rounded-2xl border border-border bg-surface shadow-xs overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 md:px-6">
          <div>
            <h2 className="font-heading font-bold text-lg text-navy">
              Jejak wewenang admin
            </h2>
            <p className="mt-1 text-xs text-muted">
              Catatan permanen atas tindakan admin pada akun. Entri terbaru
              ditampilkan lebih dulu.
            </p>
          </div>
          <span className="text-xs text-muted">{traceTotal} entri</span>
        </div>
        {Boolean(traceError) && (
          <div
            role="alert"
            className="mx-5 mt-4 flex items-start gap-2 rounded-xl border border-orange/30 bg-white p-3 text-sm text-orange md:mx-6"
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>
              {authErrorMessage(
                traceError,
                "Jejak wewenang admin tidak dapat dimuat.",
              )}
            </span>
          </div>
        )}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-secondary text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Waktu</th>
                <th className="px-4 py-3 font-semibold">Aktor</th>
                <th className="px-4 py-3 font-semibold">Target</th>
                <th className="px-4 py-3 font-semibold">Aksi</th>
                <th className="px-4 py-3 font-semibold">Kolom</th>
                <th className="px-4 py-3 font-semibold">Nilai lama</th>
                <th className="px-4 py-3 font-semibold">Nilai baru</th>
                <th className="px-4 py-3 font-semibold">Alasan</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {traceLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-muted">
                    Memuat jejak wewenang admin
                  </td>
                </tr>
              ) : traces.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-muted">
                    Belum ada jejak wewenang admin. Aksi pengelolaan akun akan
                    tercatat di sini.
                  </td>
                </tr>
              ) : (
                traces.map((trace) => (
                  <tr key={trace.trace_id} className="align-top">
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-muted">
                      {traceTimeLabel(trace.created_at)}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {traceSnapshotLabel(trace.actor_snapshot)}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {traceSnapshotLabel(trace.target_snapshot)}
                    </td>
                    <td className="px-4 py-3 text-navy">
                      {TRACE_ACTION_LABELS[trace.action] ?? trace.action}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted">
                      {trace.field_name ?? "Tidak ada"}
                    </td>
                    <td className="break-words px-4 py-3 font-mono text-xs text-muted">
                      {trace.old_value ?? "Tidak ada"}
                    </td>
                    <td className="break-words px-4 py-3 font-mono text-xs text-muted">
                      {trace.new_value ?? "Tidak ada"}
                    </td>
                    <td className="break-words px-4 py-3 text-xs text-muted">
                      {trace.reason ?? "Tidak ada"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3">
          <p className="text-xs text-muted">
            Halaman {tracePage} dari {Math.max(1, tracePages)}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Halaman jejak sebelumnya"
              disabled={tracePage <= 1 || traceLoading}
              onClick={() => setTracePage((value) => Math.max(1, value - 1))}
              className={cn(
                ADMIN_ACTION_CLASS,
                "min-w-11 border border-border bg-background text-navy hover:bg-secondary px-2",
              )}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              aria-label="Halaman jejak berikutnya"
              disabled={tracePage >= tracePages || traceLoading}
              onClick={() =>
                setTracePage((value) => Math.min(tracePages, value + 1))
              }
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

      {action && (
        <ConfirmDialog
          key={`${action.kind}-${action.account.user_id}`}
          labelledBy="admin-confirm-dialog-title"
          title={
            action.kind === "status"
              ? action.nextActive
                ? "Aktifkan Akun"
                : "Nonaktifkan Akun"
              : action.kind === "reset"
                ? "Reset Kata Sandi"
                : "Anonimisasi Akun"
          }
          body={
            <div className="space-y-3">
              <div className="rounded-xl border border-border bg-background p-3">
                <p className="font-semibold text-navy">
                  {action.account.full_name || "Tidak tersedia"}
                </p>
                <dl className="mt-2 grid gap-1 text-xs text-muted sm:grid-cols-2">
                  <div>
                    <dt className="inline font-medium">NIM: </dt>
                    <dd className="inline font-mono">
                      {action.account.student_number ?? "Tidak tersedia"}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline font-medium">Program studi: </dt>
                    <dd className="inline">
                      {action.account.study_program ?? "Tidak tersedia"}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline font-medium">Angkatan: </dt>
                    <dd className="inline">
                      {action.account.admission_year ?? "Tidak tersedia"}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline font-medium">Semester aktif: </dt>
                    <dd className="inline">
                      {action.account.current_semester ?? "Tidak tersedia"}
                    </dd>
                  </div>
                </dl>
              </div>
              {action.kind === "status" ? (
                action.nextActive ? (
                  <p className="text-sm text-muted">
                    Akun dapat masuk kembali setelah aktivasi. Token lama tidak
                    akan hidup kembali.
                  </p>
                ) : (
                  <p className="text-sm text-orange">
                    Akun menjadi akun nonaktif: login terblokir dan sesi aktif
                    terputus. Riwayat akademik tetap tersimpan.
                  </p>
                )
              ) : action.kind === "reset" ? (
                <p className="text-sm text-muted">
                  Kata sandi sementara baru akan dibuat dan sesi akun terkait
                  dicabut. Kredensial hanya berubah setelah konfirmasi.
                </p>
              ) : (
                <p className="text-sm text-orange">
                  Akun dianonimisasi: data pribadi dibersihkan permanen, tetapi
                  baris akun dan riwayat akademik tetap tersimpan.
                </p>
              )}
            </div>
          }
          confirmLabel={
            action.kind === "status"
              ? action.nextActive
                ? "Aktifkan akun"
                : "Nonaktifkan akun"
              : action.kind === "reset"
                ? "Reset kata sandi"
                : "Anonimisasi akun"
          }
          reasonField={
            action.kind === "anonymize" ||
            (action.kind === "status" && !action.nextActive)
              ? {
                  required: true,
                  label:
                    action.kind === "anonymize"
                      ? "Alasan anonimisasi"
                      : "Alasan penonaktifan",
                  placeholder: "Tuliskan alasan tindakan ini",
                }
              : {
                  required: false,
                  label: "Alasan",
                  placeholder: "Tuliskan alasan jika perlu",
                }
          }
          manualField={
            action.kind === "anonymize"
              ? {
                  expected: dialogConfirmationTarget,
                  label:
                    action.account.role === "student"
                      ? `Ketik NIM ${dialogConfirmationTarget} untuk mengonfirmasi.`
                      : `Ketik email ${dialogConfirmationTarget} untuk mengonfirmasi.`,
                  placeholder: "Ketik identitas akun dengan tepat",
                }
              : undefined
          }
          tone={
            action.kind === "status" && action.nextActive ? "navy" : "orange"
          }
          busy={actionBusy}
          errorMessage={actionError}
          onConfirm={(values) => void confirmAction(values)}
          onCancel={() => setAction(null)}
        />
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
  const [activePage, setActivePage] = useState<Page>(pageFromLocation)
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
  const hasBeenLoggedIn = useRef(isLoggedIn)

  const navigate = useCallback((page: Page, replace = false) => {
    const url = pageUrlWithContext(page)
    if (replace) {
      window.history.replaceState(null, "", url)
    } else {
      window.history.pushState(null, "", url)
    }
    setActivePage(page)
  }, [])

  useEffect(() => {
    const syncFromLocation = () => {
      const pathname = pathSegment()
      const page = pageFromLocation()
      if (pathname !== "" && !isPage(pathname)) {
        window.history.replaceState(null, "", pageUrlWithContext("dashboard"))
      }
      setActivePage(page)
    }
    syncFromLocation()
    window.addEventListener("popstate", syncFromLocation)
    return () => window.removeEventListener("popstate", syncFromLocation)
  }, [])
  useEffect(() => {
    if (isLoggedIn && !canAccess(activePage)) navigate("dashboard", true)
  }, [activePage, canAccess, isLoggedIn, navigate])
  useEffect(() => {
    if (isLoggedIn) {
      hasBeenLoggedIn.current = true
      return
    }
    if (!hasBeenLoggedIn.current) return
    hasBeenLoggedIn.current = false
    setChatMessages(INITIAL_CHAT_MESSAGES)
    setChatProfile(INITIAL_STUDENT_PROFILE)
    setChatAppliedPlanId(null)
    setIsLogoutModalOpen(false)
    navigate("dashboard", true)
  }, [isLoggedIn, navigate])
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
    const validPage = isPage(page) ? page : "dashboard"
    setPlannerInitialTab(options?.tab || "roadmap")
    setFinderInitialCourse(options?.course || null)
    navigate(validPage)
  }

  const handleAnchorNavigate = (
    event: MouseEvent<HTMLAnchorElement>,
    page: Page,
  ) => {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }
    event.preventDefault()
    handleNavigate(page)
    if (window.innerWidth < 768) setIsSidebarOpen(false)
  }

  const visiblePage = canAccess(activePage) ? activePage : "dashboard"

  const handleApplyPlanFromChatbot = (payload: DegreePlanPayload) => {
    planner.applyPlan(payload)
    handleNavigate("degree-planner")
  }

  const handleLogout = () => {
    logout()
    setIsLogoutModalOpen(false)
  }

  const addedCourseIds = new Set(
    planner.pendingCourses.map((course) => course.id),
  )

  const navItems = useMemo(() => {
    const role = user?.role || "student"
    if (role === "lecturer") {
      return [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "pj-courses", label: "Rekap & Kelola MK", icon: BookOpen },
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
          navigate("dashboard", true)
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
              const isActive = visiblePage === item.id
              return (
                <a
                  key={item.id}
                  href={pageUrlWithContext(item.id)}
                  onClick={(event) => handleAnchorNavigate(event, item.id)}
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
                </a>
              )
            })}
          </nav>

          <div className="p-4 border-t border-navy-light/50">
            <div
              className={cn(
                "flex items-center gap-2 p-1.5 rounded-xl transition-all",
                visiblePage === "profile"
                  ? "bg-navy-light border border-gold/40 text-white shadow-xs"
                  : "hover:bg-navy-light/50 text-teal-light hover:text-white border border-transparent",
              )}
            >
              <a
                href={pageUrlWithContext("profile")}
                onClick={(event) => handleAnchorNavigate(event, "profile")}
                className="flex items-center gap-3 flex-1 min-w-0 text-left cursor-pointer group p-1 rounded-lg"
                title="Buka Halaman Profil Pengguna"
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 font-heading font-bold text-xs transition-transform group-hover:scale-105",
                    visiblePage === "profile"
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
              </a>

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
              {visiblePage === "admin-accounts"
                ? "Manajemen Akun"
                : visiblePage === "pj-courses"
                  ? "Rekap & Kelola MK"
                  : visiblePage === "chatbot"
                    ? "Compass AI"
                    : visiblePage === "profile"
                      ? "Profil Pengguna"
                      : visiblePage === "course-finder" &&
                          user?.role === "admin"
                        ? "Course Management"
                        : visiblePage.replace("-", " ")}
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
            visiblePage === "degree-planner"
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
              visiblePage === "degree-planner"
                ? "w-full max-w-none"
                : "max-w-7xl",
            )}
          >
            <ErrorBoundary key={visiblePage}>
              {visiblePage === "dashboard" && (
                <Dashboard onNavigate={handleNavigate} />
              )}
              {visiblePage === "course-finder" && (
                <CourseFinder
                  onAddToPlanner={planner.addPendingCourse}
                  addedCourseIds={addedCourseIds}
                  initialCourse={finderInitialCourse}
                  onClearInitialCourse={() => setFinderInitialCourse(null)}
                />
              )}
              {visiblePage === "pj-courses" && user?.role === "lecturer" && (
                <PjCoursesPage onNavigate={handleNavigate} />
              )}
              {visiblePage === "degree-planner" && (
                <DegreePlanner
                  onNavigate={handleNavigate}
                  initialTab={plannerInitialTab}
                />
              )}
              {visiblePage === "chatbot" && (
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
              {visiblePage === "profile" && (
                <Profile
                  onNavigate={handleNavigate}
                  onRequestLogout={() => setIsLogoutModalOpen(true)}
                />
              )}
              {visiblePage === "admin-accounts" && user?.role === "admin" && (
                <AdminAccounts />
              )}
            </ErrorBoundary>
          </div>
        </div>
      </main>

      {isLogoutModalOpen && (
        <ConfirmDialog
          labelledBy="logout-dialog-title"
          title="Konfirmasi Keluar"
          body={
            <p className="text-xs text-muted leading-relaxed">
              Apakah Anda yakin ingin mengakhiri sesi akademik di FTMM Compass?
              Anda dapat masuk kembali kapan saja dengan akun Cybercampus UNAIR.
            </p>
          }
          cancelLabel="Batal"
          confirmLabel="Ya, Keluar"
          tone="orange"
          icon={
            <div className="w-12 h-12 rounded-full bg-orange/10 text-orange flex items-center justify-center mx-auto border border-orange/20">
              <LogOut className="w-6 h-6" />
            </div>
          }
          panelClassName="bg-surface rounded-2xl border border-border shadow-2xl max-w-sm w-full p-6 space-y-4 animate-in zoom-in-95 duration-200"
          overlayClassName="bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
          onConfirm={handleLogout}
          onCancel={() => setIsLogoutModalOpen(false)}
        />
      )}
    </div>
  )
}
