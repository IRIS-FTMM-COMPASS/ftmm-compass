import { ApiError, apiFetch, authHeaders } from "@/shared/api/client"
import {
  clearSession,
  readToken,
  readUser,
  writeToken,
  writeUser,
} from "@/shared/api/session"

export interface LoginCredentials {
  identifier: string
  password: string
}

export interface StudentProfile {
  student_number: string
  study_program: string
  program_code: string
  admission_year: number
  current_semester: number
}

export interface AuthUser {
  user_id: string
  email: string
  full_name: string
  role: string
  auth_provider?: string
  academic_identifier?: string
  unit_name?: string
  phone_number?: string
  bio?: string
  career_interests?: string[]
  permissions?: string[]
  student_profile?: StudentProfile
  is_program_coordinator?: boolean
}

export interface ProfileUpdatePayload {
  phone_number?: string
  bio?: string
  career_interests?: string[]
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

export interface RegisterPayload {
  email: string
  full_name: string
  student_number: string
  admission_year: number
  password: string
}

export interface RegisterResponse extends AuthResponse {
  recovery_code: string
}

export interface RecoverPayload {
  recovery_code: string
  new_password: string
}

export interface RecoverResponse {
  message?: string
  recovery_code?: string
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
}

export interface ChangePasswordResponse {
  access_token: string
  token_type: string
  expires_in: number
  message?: string
}

export interface AdminAccount {
  user_id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  status: "active" | "inactive"
  student_number: string | null
  study_program_id: string | null
  study_program: string | null
  admission_year: number | null
  current_semester: number | null
  needs_revalidation: boolean
  anonymized_at: string | null
  created_at?: string | null
}

export interface AdminAcademicIdentityUpdate {
  study_program_id: string
  admission_year: number
  student_number: string
  current_semester: number
  reason: string
}

export interface AdminAuthorityTrace {
  trace_id: string
  actor_user_id: string
  actor_snapshot: string
  target_user_id: string
  target_snapshot: string
  action: string
  field_name: string | null
  old_value: string | null
  new_value: string | null
  reason: string | null
  created_at: string
}

export interface AdminAuthorityTraceList {
  items: AdminAuthorityTrace[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface AdminAuthorityTraceFilters {
  page?: number
  page_size?: number
}

export interface AdminAccountList {
  items: AdminAccount[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface AdminAccountFilters {
  search?: string
  role?: string
  status?: string
  page?: number
  page_size?: number
}

export interface ResetPasswordResponse {
  message?: string
  temporary_password: string
}

export interface FieldIssue {
  field: string
  message: string
  code?: string
}

export class AuthApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null,
    readonly details: FieldIssue[],
    readonly retryAfter: number | null,
  ) {
    super(message)
    this.name = "AuthApiError"
  }
}

type TokenRenewedListener = (expiresInSeconds: number) => void

const tokenRenewedListeners = new Set<TokenRenewedListener>()

export function onTokenRenewed(listener: TokenRenewedListener): () => void {
  tokenRenewedListeners.add(listener)
  return () => tokenRenewedListeners.delete(listener)
}

function notifyTokenRenewed(expiresInSeconds: number): void {
  tokenRenewedListeners.forEach((listener) => listener(expiresInSeconds))
}

function normalizeDetails(raw: unknown): FieldIssue[] {
  if (!Array.isArray(raw)) return []
  const issues: FieldIssue[] = []
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue
    const item = entry as Record<string, unknown>
    let field = ""
    if (typeof item.field === "string") {
      field = item.field
    } else if (Array.isArray(item.loc)) {
      const parts = item.loc.filter(
        (part) => part !== "body" && part !== "query" && part !== "path",
      )
      field = String(parts[parts.length - 1] ?? "")
    }
    const message =
      typeof item.message === "string"
        ? item.message
        : typeof item.msg === "string"
          ? item.msg
          : ""
    if (!field || !message) continue
    issues.push({
      field,
      message,
      code: typeof item.code === "string" ? item.code : undefined,
    })
  }
  return issues
}

export function authErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AuthApiError || error instanceof ApiError) {
    return error.message || fallback
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof AuthApiError)) return {}
  return Object.fromEntries(
    error.details.map((issue) => [issue.field, issue.message]),
  )
}

export function fieldError(error: unknown, name: string): string | null {
  return fieldErrors(error)[name] ?? null
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE"
  body?: unknown
  auth?: boolean
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  try {
    return await apiFetch<T>(path, {
      method: options.method,
      body: options.body,
      auth: options.auth !== false,
    })
  } catch (error) {
    if (error instanceof ApiError) {
      throw new AuthApiError(
        error.message,
        error.status,
        error.code ?? null,
        normalizeDetails(error.details),
        error.retryAfter,
      )
    }
    throw new AuthApiError(
      "Tidak dapat terhubung ke layanan. Silakan coba lagi.",
      0,
      null,
      [],
      null,
    )
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? value as Record<string, unknown>
    : {}
}
function nullableString(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null
}

function nullableInteger(value: unknown): number | null {
  if (typeof value === "number" && Number.isInteger(value)) return value
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value)
    if (Number.isInteger(parsed)) return parsed
  }
  return null
}

function traceText(value: unknown): string | null {
  if (value === null || value === undefined) return null
  return typeof value === "string" ? value : String(value)
}
function normalizeAccount(value: unknown): AdminAccount {
  const item = asRecord(value)
  const profile = asRecord(item.student_profile)
  const pick = (key: string): unknown => item[key] ?? profile[key]
  const isActive =
    typeof item.is_active === "boolean"
      ? item.is_active
      : item.status === "active"
  return {
    user_id: String(item.user_id ?? item.id ?? ""),
    email: String(item.email ?? ""),
    full_name: String(item.full_name ?? ""),
    role: String(item.role ?? "student"),
    is_active: isActive,
    status: isActive ? "active" : "inactive",
    student_number: nullableString(pick("student_number")),
    study_program_id: nullableString(pick("study_program_id")),
    study_program: nullableString(pick("study_program")),
    admission_year: nullableInteger(pick("admission_year")),
    current_semester: nullableInteger(pick("current_semester")),
    needs_revalidation: pick("needs_revalidation") === true,
    anonymized_at: nullableString(item.anonymized_at),
    created_at: nullableString(item.created_at),
  }
}

function normalizeAccountList(value: unknown): AdminAccountList {
  const body = asRecord(value)
  const source = Array.isArray(body.data)
    ? body.data
    : Array.isArray(body.items)
      ? body.items
      : []
  const items = source.map(normalizeAccount)
  const meta = asRecord(body.meta)
  const total = Number(meta.total ?? body.total ?? items.length)
  const page = Math.max(1, Number(meta.page ?? body.page ?? 1))
  const page_size = Number(meta.page_size ?? body.per_page ?? 20)
  const pages = Math.max(
    1,
    Number(meta.pages ?? Math.ceil(total / Math.max(1, page_size))),
  )
  return { items, total, page, page_size, pages }
}

function normalizeTrace(value: unknown): AdminAuthorityTrace {
  const item = asRecord(value)
  return {
    trace_id: traceText(item.trace_id) ?? "",
    actor_user_id: traceText(item.actor_user_id) ?? "",
    actor_snapshot: traceText(item.actor_snapshot) ?? "",
    target_user_id: traceText(item.target_user_id) ?? "",
    target_snapshot: traceText(item.target_snapshot) ?? "",
    action: traceText(item.action) ?? "",
    field_name: traceText(item.field_name),
    old_value: traceText(item.old_value),
    new_value: traceText(item.new_value),
    reason: traceText(item.reason),
    created_at: traceText(item.created_at) ?? "",
  }
}

function normalizeTraceList(value: unknown): AdminAuthorityTraceList {
  const body = asRecord(value)
  const source = Array.isArray(body.data)
    ? body.data
    : Array.isArray(body.items)
      ? body.items
      : []
  const items = source.map(normalizeTrace)
  const meta = asRecord(body.meta)
  const total = Number(meta.total ?? body.total ?? items.length)
  const page = Math.max(1, Number(meta.page ?? body.page ?? 1))
  const page_size = Number(meta.page_size ?? body.per_page ?? 20)
  const pages = Math.max(
    1,
    Number(meta.pages ?? Math.ceil(total / Math.max(1, page_size))),
  )
  return { items, total, page, page_size, pages }
}

export async function copyToClipboard(value: string): Promise<boolean> {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {
    return false
  }
  return false
}

export function downloadTextFile(filename: string, content: string): void {
  if (typeof document === "undefined") return
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const data = await request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: credentials,
      auth: false,
    })
    writeToken(data.access_token)
    writeUser(data.user)
    return data
  },

  async register(payload: RegisterPayload): Promise<RegisterResponse> {
    const data = await request<RegisterResponse>("/api/v1/auth/register", {
      method: "POST",
      body: payload,
      auth: false,
    })
    writeToken(data.access_token)
    writeUser(data.user)
    return data
  },

  async recover(payload: RecoverPayload): Promise<RecoverResponse> {
    return request<RecoverResponse>("/api/v1/auth/recover", {
      method: "POST",
      body: payload,
      auth: false,
    })
  },

  async changePassword(
    payload: ChangePasswordPayload,
  ): Promise<ChangePasswordResponse> {
    const data = await request<ChangePasswordResponse>(
      "/api/v1/auth/change-password",
      { method: "POST", body: payload },
    )
    writeToken(data.access_token)
    notifyTokenRenewed(data.expires_in)
    return data
  },

  getStoredUser(): AuthUser | null {
    return readUser<AuthUser>()
  },

  getStoredToken(): string | null {
    return readToken()
  },

  logout(): void {
    clearSession()
  },

  getAuthHeaders(): Record<string, string> {
    return authHeaders()
  },

  async getMe(): Promise<AuthUser> {
    if (!readToken()) throw new ApiError("Sesi tidak ditemukan", 401)
    const user = await request<AuthUser>("/api/v1/auth/me")
    writeUser(user)
    return user
  },

  async updateProfile(payload: ProfileUpdatePayload): Promise<AuthUser> {
    if (!readToken()) throw new ApiError("Sesi tidak ditemukan", 401)
    const user = await request<AuthUser>("/api/v1/auth/me/profile", {
      method: "PATCH",
      body: payload,
    })
    writeUser(user)
    return user
  },

  async listAccounts(
    filters: AdminAccountFilters = {},
  ): Promise<AdminAccountList> {
    const params = new URLSearchParams()
    if (filters.search?.trim()) params.set("search", filters.search.trim())
    if (filters.role && filters.role !== "all") params.set("role", filters.role)
    if (filters.status && filters.status !== "all") {
      params.set("status", filters.status)
    }
    params.set("page", String(filters.page ?? 1))
    params.set("page_size", String(filters.page_size ?? 20))
    const raw = await request<unknown>(`/api/v1/admin/accounts?${params}`)
    return normalizeAccountList(raw)
  },

  async setAccountStatus(
    userId: string,
    isActive: boolean,
    reason?: string,
  ): Promise<AdminAccount> {
    const trimmedReason = reason?.trim()
    const raw = await request<unknown>(
      `/api/v1/admin/accounts/${encodeURIComponent(userId)}`,
      {
        method: "PATCH",
        body: {
          is_active: isActive,
          ...(trimmedReason ? { reason: trimmedReason } : {}),
        },
      },
    )
    const body = asRecord(raw)
    return normalizeAccount(body.data ?? raw)
  },

  async resetAccountPassword(
    userId: string,
    reason?: string,
  ): Promise<ResetPasswordResponse> {
    const trimmedReason = reason?.trim()
    const raw = await request<unknown>(
      `/api/v1/admin/accounts/${encodeURIComponent(userId)}/reset-password`,
      {
        method: "POST",
        ...(trimmedReason ? { body: { reason: trimmedReason } } : {}),
      },
    )
    const body = asRecord(raw)
    return {
      message: typeof body.message === "string" ? body.message : undefined,
      temporary_password:
        typeof body.temporary_password === "string"
          ? body.temporary_password
          : "",
    }
  },

  async getAcademicIdentity(userId: string): Promise<AdminAccount> {
    const raw = await request<unknown>(
      `/api/v1/admin/accounts/${encodeURIComponent(userId)}/profile`,
    )
    const body = asRecord(raw)
    return normalizeAccount(body.data ?? raw)
  },

  async updateAcademicIdentity(
    userId: string,
    payload: AdminAcademicIdentityUpdate,
  ): Promise<AdminAccount> {
    const raw = await request<unknown>(
      `/api/v1/admin/accounts/${encodeURIComponent(userId)}/profile`,
      { method: "PATCH", body: payload },
    )
    const body = asRecord(raw)
    return normalizeAccount(body.data ?? raw)
  },

  async anonymizeAccount(
    userId: string,
    confirmation: string,
    reason: string,
  ): Promise<AdminAccount> {
    const raw = await request<unknown>(
      `/api/v1/admin/accounts/${encodeURIComponent(userId)}/anonymize`,
      {
        method: "POST",
        body: { confirmation, reason: reason.trim() },
      },
    )
    const body = asRecord(raw)
    return normalizeAccount(body.data ?? raw)
  },

  async listAuthorityTraces(
    filters: AdminAuthorityTraceFilters = {},
  ): Promise<AdminAuthorityTraceList> {
    const params = new URLSearchParams()
    params.set("page", String(filters.page ?? 1))
    params.set("page_size", String(filters.page_size ?? 20))
    const raw = await request<unknown>(
      `/api/v1/admin/authority-traces?${params}`,
    )
    return normalizeTraceList(raw)
  },
}
