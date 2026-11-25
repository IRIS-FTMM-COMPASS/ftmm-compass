import { clearSession, readToken } from "./session"

export const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(
  /\/+$/,
  "",
)

export interface ApiFieldIssue {
  field: string
  message: string
  code?: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly details: unknown = undefined,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export interface ApiRequest {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  auth?: boolean
  headers?: Record<string, string>
  signal?: AbortSignal
}

interface ErrorEnvelope {
  error?: {
    message?: unknown
    code?: unknown
    details?: unknown
  }
  detail?: unknown
  message?: unknown
  code?: unknown
  details?: unknown
}

interface ParsedErrorEnvelope {
  message: string
  code?: string
  details: unknown
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined
}

function fieldFrom(item: Record<string, unknown>): string {
  const field = stringValue(item.field)
  if (field) {
    const name = field.replace(/^body\./, "")
    return name === "body" || name === "query" || name === "path" ? "" : name
  }
  if (!Array.isArray(item.loc)) return ""
  const parts = item.loc.filter(
    (part): part is string | number =>
      (typeof part === "string" || typeof part === "number") &&
      part !== "body" &&
      part !== "query" &&
      part !== "path",
  )
  return String(parts[parts.length - 1] ?? "")
}

export function apiFieldErrors(error: unknown): ApiFieldIssue[] {
  if (!error || typeof error !== "object" || !("details" in error)) return []
  const details = error.details
  if (!Array.isArray(details)) return []
  const issues: ApiFieldIssue[] = []
  for (const entry of details) {
    if (!entry || typeof entry !== "object") continue
    const item = entry as Record<string, unknown>
    const field = fieldFrom(item)
    const message = stringValue(item.message) ?? stringValue(item.msg)
    if (!field || !message) continue
    const code = stringValue(item.code) ?? stringValue(item.type)
    issues.push(code ? { field, message, code } : { field, message })
  }
  return issues
}

function parseErrorEnvelope(
  payload: unknown,
  status: number,
  fallback: string,
): ParsedErrorEnvelope {
  let message: string | undefined
  let code: string | undefined
  let details: unknown
  if (payload && typeof payload === "object") {
    const body = payload as ErrorEnvelope
    const envelope =
      body.error && typeof body.error === "object" ? body.error : undefined
    details = envelope?.details ?? body.details ?? body.detail
    code = stringValue(envelope?.code) ?? stringValue(body.code)
    message =
      stringValue(envelope?.message) ??
      stringValue(body.detail) ??
      stringValue(body.message)
    if (status === 422 && message === "Request validation failed") {
      message = undefined
    }
    if (!message && typeof details === "string") message = stringValue(details)
    if (!message && details && status !== 422) message = JSON.stringify(details)
  }
  return { message: message ?? fallback, code, details }
}

export function authHeaders(): Record<string, string> {
  const token = readToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function apiFetch<T>(
  path: string,
  request: ApiRequest = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(request.auth ? authHeaders() : {}),
    ...request.headers,
  }
  let body: BodyInit | undefined
  if (request.body instanceof FormData) {
    body = request.body
  } else if (request.body !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(request.body)
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: request.method ?? "GET",
    headers,
    body,
    signal: request.signal,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const fallback =
      response.status === 422
        ? "Data yang dikirim tidak valid."
        : `Permintaan gagal (${response.status})`
    const parsed = parseErrorEnvelope(payload, response.status, fallback)
    const message =
      response.status >= 500
        ? `Layanan sedang bermasalah (${response.status})`
        : parsed.message
    if (response.status === 401 && request.auth) clearSession()
    throw new ApiError(message, response.status, parsed.code, parsed.details)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}
