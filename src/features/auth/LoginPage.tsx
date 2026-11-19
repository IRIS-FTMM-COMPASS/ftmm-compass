import { useState, type FormEvent } from "react"
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Check,
  Compass,
  Copy,
  KeyRound,
  Download,
  Lock,
  Mail,
  User,
} from "lucide-react"
import {
  AuthApiError,
  authService,
  authErrorMessage,
  copyToClipboard,
  downloadTextFile,
  fieldError,
  type AuthUser,
} from "@/features/auth/authService"
import DevAccountPicker from "@/features/auth/components/DevAccountPicker"
import { cn } from "@/shared/utils"

import BrandLogo from "@/shared/ui/BrandLogo"

interface LoginProps {
  onLogin: (user: AuthUser, expiresInSeconds?: number) => void
}

type Mode = "login" | "register" | "recover"

interface PendingSession {
  user: AuthUser
  expiresInSeconds: number
}

const MODE_COPY: Record<Mode, {
  title: string
  subtitle: string
  submit: string
}> = {
  login: {
    title: "Selamat Datang",
    subtitle: "Gunakan akun Cybercampus UNAIR untuk masuk",
    submit: "Masuk ke Dashboard",
  },
  register: {
    title: "Daftar Akun Baru",
    subtitle: "Gunakan email institusi yang valid untuk mendaftar",
    submit: "Buat Akun Mahasiswa",
  },
  recover: {
    title: "Pemulihan Kata Sandi",
    subtitle: "Masukkan kode pemulihan untuk mengatur ulang kata sandi",
    submit: "Perbarui Kata Sandi",
  },
}

const INACTIVE_ACCOUNT_MESSAGE = "Akun Anda dinonaktifkan oleh admin"

function isInactiveAccountError(error: unknown): boolean {
  if (!(error instanceof AuthApiError)) return false
  return (
    error.code === "account_inactive" ||
    error.message === INACTIVE_ACCOUNT_MESSAGE
  )
}

interface FieldMessageProps {
  message: string | null
  id?: string
}
const CURRENT_YEAR = new Date().getFullYear()

const INPUT_CLASS =
  "w-full min-h-11 rounded-xl border border-border bg-surface px-4 text-foreground placeholder:text-muted focus:border-gold focus:ring-1 focus:ring-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 transition-all disabled:opacity-70"

const ICON_INPUT_CLASS =
  "w-full min-h-11 rounded-xl border border-border bg-surface pl-10 pr-4 text-foreground placeholder:text-muted focus:border-gold focus:ring-1 focus:ring-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 transition-all disabled:opacity-70"

const ACTION_CLASS =
  "min-h-11 w-full flex justify-center items-center gap-2 px-4 rounded-xl font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2 disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer"

function FieldMessage({ message, id }: FieldMessageProps) {
  if (!message) return null
  return (
    <p id={id} className="mt-1 text-xs text-orange" role="alert">
      {message}
    </p>
  )
}

interface RecoveryCodePanelProps {
  code: string
  title: string
  description: string
  actionLabel: string
  onAction: () => void
}

function RecoveryCodePanel({
  code,
  title,
  description,
  actionLabel,
  onAction,
}: RecoveryCodePanelProps) {
  const [copyMessage, setCopyMessage] = useState<string | null>(null)

  const handleCopy = async () => {
    const copied = await copyToClipboard(code)
    setCopyMessage(
      copied
        ? "Kode berhasil disalin."
        : "Kode tidak dapat disalin otomatis. Silakan salin secara manual.",
    )
  }

  const handleDownload = () => {
    downloadTextFile(
      "kode-pemulihan-ftmm-compass.txt",
      `Kode Pemulihan FTMM Compass\n\nKode: ${code}\n\nSimpan kode ini di tempat yang aman. Kode ini hanya ditampilkan sekali.\n`,
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex justify-center">
        <div className="w-12 h-12 rounded-full bg-gold/10 text-gold flex items-center justify-center border border-gold/30">
          <Check className="w-6 h-6" />
        </div>
      </div>
      <div className="text-center space-y-1">
        <h2 className="text-2xl font-heading font-bold text-navy">{title}</h2>
        <p className="text-sm text-muted leading-relaxed">{description}</p>
      </div>

      <div className="rounded-xl border border-gold/40 bg-background p-4">
        <p className="text-xs font-semibold text-muted mb-2">Kode Pemulihan</p>
        <code className="block font-mono text-lg text-navy break-all select-all">
          {code}
        </code>
      </div>
      <p className="text-xs text-orange" role="alert">
        Kode ini hanya ditampilkan sekali. Salin atau unduh sebelum melanjutkan.
      </p>

      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => void handleCopy()}
          className={cn(
            ACTION_CLASS,
            "border border-border bg-surface text-navy hover:bg-secondary",
          )}
        >
          <Copy className="w-4 h-4" /> Salin kode
        </button>
        <button
          type="button"
          onClick={handleDownload}
          className={cn(
            ACTION_CLASS,
            "border border-border bg-surface text-navy hover:bg-secondary",
          )}
        >
          <Download className="w-4 h-4" /> Unduh kode
        </button>
      </div>
      {copyMessage && (
        <p className="text-xs text-navy text-center" role="status">
          {copyMessage}
        </p>
      )}

      <button
        type="button"
        onClick={onAction}
        className={cn(ACTION_CLASS, "bg-navy text-white hover:bg-navy-light")}
      >
        {actionLabel} <ArrowRight className="w-5 h-5" />
      </button>
    </div>
  )
}

export default function Login({ onLogin }: LoginProps) {
  const [mode, setMode] = useState<Mode>("login")
  const [nim, setNim] = useState("")
  const [password, setPassword] = useState("")
  const [registerForm, setRegisterForm] = useState({
    email: "",
    full_name: "",
    student_number: "",
    admission_year: "",
    password: "",
  })
  const [recoverForm, setRecoverForm] = useState({
    recovery_code: "",
    new_password: "",
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [pendingSession, setPendingSession] = useState<PendingSession | null>(
    null,
  )
  const [recoveryCode, setRecoveryCode] = useState<string | null>(null)
  const [recoveredCode, setRecoveredCode] = useState<string | null>(null)

  const switchMode = (next: Mode) => {
    setMode(next)
    setError(null)
    setNotice(null)
  }

  const fallbackMessage =
    mode === "register"
      ? "Pendaftaran gagal. Silakan coba lagi."
      : mode === "recover"
        ? "Pemulihan kata sandi gagal. Silakan coba lagi."
        : "Terjadi kesalahan saat masuk. Silakan coba lagi."
  const errorMessage = error ? authErrorMessage(error, fallbackMessage) : null
  const isAccountInactive = mode === "login" && isInactiveAccountError(error)

  const performLogin = async (identifier: string, passwordValue: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await authService.login({
        identifier,
        password: passwordValue,
      })
      onLogin(response.user, response.expires_in)
    } catch (err: unknown) {
      setError(err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    await performLogin(nim.trim(), password)
  }

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const response = await authService.register({
        email: registerForm.email.trim(),
        full_name: registerForm.full_name.trim(),
        student_number: registerForm.student_number.trim(),
        admission_year: Number(registerForm.admission_year),
        password: registerForm.password,
      })
      setPendingSession({
        user: response.user,
        expiresInSeconds: response.expires_in,
      })
      setRecoveryCode(response.recovery_code)
    } catch (err: unknown) {
      setError(err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleRecover = async (e: FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const response = await authService.recover({
        recovery_code: recoverForm.recovery_code.trim(),
        new_password: recoverForm.new_password,
      })
      setRecoverForm({ recovery_code: "", new_password: "" })
      setRecoveredCode(response.recovery_code ?? "")
      setNotice(response.message ?? "Kata sandi berhasil diperbarui.")
    } catch (err: unknown) {
      setError(err)
    } finally {
      setIsLoading(false)
    }
  }

  const enterDashboard = () => {
    if (pendingSession) {
      onLogin(pendingSession.user, pendingSession.expiresInSeconds)
    }
    setPendingSession(null)
    setRecoveryCode(null)
  }

  const backToLogin = () => {
    setRecoveredCode(null)
    setNotice(null)
    setError(null)
    setMode("login")
  }

  const hero = (
    <div className="hidden lg:flex w-1/2 bg-navy relative overflow-hidden flex-col justify-between p-12">
      <div className="absolute inset-0 z-0 bg-gradient-to-br from-navy-dark via-navy to-navy-light/90">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-gold/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-teal/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(var(--color-gold)_1px,transparent_1px)] [background-size:24px_24px] opacity-[0.04]" />
      </div>

      <div className="relative z-10 flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-gold/10 flex items-center justify-center text-gold border border-gold/30">
          <Compass className="w-7 h-7" />
        </div>
        <div>
          <h1 className="font-heading font-bold text-xl text-gold tracking-wide">
            FTMM COMPASS
          </h1>
          <p className="text-xs text-teal-light uppercase tracking-wider font-mono">
            Academic Advisor
          </p>
        </div>
      </div>

      <div className="relative z-10 max-w-lg">
        <h2 className="text-4xl font-heading font-bold text-white leading-tight mb-6">
          Navigasi Perjalanan Akademikmu Bersama FTMM
        </h2>
        <p className="text-teal-light text-lg mb-8">
          Platform penasihat akademik terpadu untuk mahasiswa Fakultas Teknologi
          Maju dan Multidisiplin Universitas Airlangga. Susun rencana studi,
          atur jadwal, dan capai target kelulusanmu.
        </p>
        <div className="flex gap-4 items-center">
          <BrandLogo variant="login-hero" />
        </div>
      </div>
    </div>
  )

  if (recoveryCode) {
    return (
      <div className="min-h-screen w-full flex bg-background font-sans">
        {hero}
        <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-surface">
          <div className="max-w-md w-full">
            <BrandLogo variant="login-form" className="lg:hidden mb-8" />
            <RecoveryCodePanel
              code={recoveryCode}
              title="Pendaftaran Berhasil"
              description="Akun mahasiswa Anda telah aktif. Kode pemulihan diperlukan untuk mengatur ulang kata sandi."
              actionLabel="Lanjut ke Dashboard"
              onAction={enterDashboard}
            />
          </div>
        </div>
      </div>
    )
  }

  if (recoveredCode) {
    return (
      <div className="min-h-screen w-full flex bg-background font-sans">
        {hero}
        <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-surface">
          <div className="max-w-md w-full">
            <BrandLogo variant="login-form" className="lg:hidden mb-8" />
            {notice && (
              <p className="mb-4 text-sm text-navy text-center" role="status">
                {notice}
              </p>
            )}
            <RecoveryCodePanel
              code={recoveredCode}
              title="Kata Sandi Diperbarui"
              description="Kode pemulihan lama tidak berlaku lagi. Gunakan kode berikut untuk pemulihan berikutnya."
              actionLabel="Kembali ke Masuk"
              onAction={backToLogin}
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen w-full flex bg-background font-sans">
      {hero}

      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-surface">
        <div className="max-w-md w-full">
          <div className="text-center mb-8">
            <BrandLogo variant="login-form" className="lg:hidden" />
            <h2 className="text-3xl font-heading font-bold text-navy mb-2">
              {MODE_COPY[mode].title}
            </h2>
            <p className="text-muted text-sm">{MODE_COPY[mode].subtitle}</p>
          </div>

          {isAccountInactive && (
            <div
              className="mb-6 p-4 rounded-xl bg-white border border-orange/40 text-orange flex items-start gap-3"
              role="alert"
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm leading-relaxed">
                <p className="font-semibold">Akun Dinonaktifkan</p>
                <p className="mt-1 text-base font-semibold">
                  {INACTIVE_ACCOUNT_MESSAGE}
                </p>
              </div>
            </div>
          )}

          {errorMessage && !isAccountInactive && (
            <div
              className="mb-6 p-4 rounded-xl bg-orange/10 border border-orange/30 text-orange flex items-start gap-3"
              role="alert"
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm leading-relaxed">
                <p className="font-semibold">Permintaan gagal</p>
                <p>{errorMessage}</p>
              </div>
            </div>
          )}

          {notice && !recoveredCode && (
            <p className="mb-4 text-sm text-navy text-center" role="status">
              {notice}
            </p>
          )}

          {mode === "login" && (
            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-1.5">
                <label
                  htmlFor="login-identifier"
                  className="text-sm font-medium text-foreground"
                >
                  NIM / Email SSO
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                  <input
                    id="login-identifier"
                    type="text"
                    required
                    autoComplete="username"
                    placeholder="Masukkan NIM atau Email"
                    className={ICON_INPUT_CLASS}
                    value={nim}
                    onChange={(e) => setNim(e.target.value)}
                    disabled={isLoading}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center gap-3">
                  <label
                    htmlFor="login-password"
                    className="text-sm font-medium text-foreground"
                  >
                    Kata Sandi
                  </label>
                  <button
                    type="button"
                    onClick={() => switchMode("recover")}
                    className="min-h-11 inline-flex items-center text-xs text-navy font-medium hover:text-gold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy rounded cursor-pointer"
                  >
                    Lupa sandi?
                  </button>
                </div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                  <input
                    id="login-password"
                    type="password"
                    required
                    autoComplete="current-password"
                    placeholder="Masukkan Kata Sandi"
                    className={ICON_INPUT_CLASS}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isLoading}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className={cn(
                  ACTION_CLASS,
                  "bg-navy text-white hover:bg-navy-light",
                )}
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    {MODE_COPY.login.submit} <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </form>
          )}

          {mode === "login" && <DevAccountPicker onSelect={performLogin} />}

          {mode === "register" && (
            <form onSubmit={handleRegister} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="register-email"
                  className="text-sm font-medium text-foreground"
                >
                  Email Institusi
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                  <input
                    id="register-email"
                    type="email"
                    required
                    autoComplete="email"
                    placeholder="nama@ftmm.unair.ac.id"
                    className={ICON_INPUT_CLASS}
                    value={registerForm.email}
                    onChange={(e) =>
                      setRegisterForm((prev) => ({
                        ...prev,
                        email: e.target.value,
                      }))
                    }
                    aria-invalid={Boolean(fieldError(error, "email"))}
                    aria-describedby="register-email-error"
                    disabled={isLoading}
                  />
                </div>
                <FieldMessage
                  id="register-email-error"
                  message={fieldError(error, "email")}
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="register-name"
                  className="text-sm font-medium text-foreground"
                >
                  Nama Lengkap
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                  <input
                    id="register-name"
                    type="text"
                    required
                    autoComplete="name"
                    placeholder="Masukkan nama lengkap"
                    className={ICON_INPUT_CLASS}
                    value={registerForm.full_name}
                    onChange={(e) =>
                      setRegisterForm((prev) => ({
                        ...prev,
                        full_name: e.target.value,
                      }))
                    }
                    aria-invalid={Boolean(fieldError(error, "full_name"))}
                    disabled={isLoading}
                  />
                </div>
                <FieldMessage message={fieldError(error, "full_name")} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label
                    htmlFor="register-nim"
                    className="text-sm font-medium text-foreground"
                  >
                    NIM
                  </label>
                  <div className="relative">
                    <BookOpen className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                    <input
                      id="register-nim"
                      type="text"
                      required
                      placeholder="Masukkan NIM"
                      className={ICON_INPUT_CLASS}
                      value={registerForm.student_number}
                      onChange={(e) =>
                        setRegisterForm((prev) => ({
                          ...prev,
                          student_number: e.target.value,
                        }))
                      }
                      aria-invalid={Boolean(
                        fieldError(error, "student_number"),
                      )}
                      disabled={isLoading}
                    />
                  </div>
                  <FieldMessage message={fieldError(error, "student_number")} />
                </div>

                <div className="space-y-1.5">
                  <label
                    htmlFor="register-year"
                    className="text-sm font-medium text-foreground"
                  >
                    Tahun Angkatan
                  </label>
                  <input
                    id="register-year"
                    type="number"
                    required
                    min={2000}
                    max={CURRENT_YEAR}
                    placeholder={String(CURRENT_YEAR)}
                    className={INPUT_CLASS}
                    value={registerForm.admission_year}
                    onChange={(e) =>
                      setRegisterForm((prev) => ({
                        ...prev,
                        admission_year: e.target.value,
                      }))
                    }
                    aria-invalid={Boolean(fieldError(error, "admission_year"))}
                    disabled={isLoading}
                  />
                  <FieldMessage message={fieldError(error, "admission_year")} />
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="register-password"
                  className="text-sm font-medium text-foreground"
                >
                  Kata Sandi
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                  <input
                    id="register-password"
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder="Minimal delapan karakter"
                    className={ICON_INPUT_CLASS}
                    value={registerForm.password}
                    onChange={(e) =>
                      setRegisterForm((prev) => ({
                        ...prev,
                        password: e.target.value,
                      }))
                    }
                    aria-invalid={Boolean(fieldError(error, "password"))}
                    disabled={isLoading}
                  />
                </div>
                <FieldMessage message={fieldError(error, "password")} />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className={cn(
                  ACTION_CLASS,
                  "bg-navy text-white hover:bg-navy-light",
                )}
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  MODE_COPY.register.submit
                )}
              </button>
            </form>
          )}

          {mode === "recover" && (
            <form onSubmit={handleRecover} className="space-y-5">
              <div className="space-y-1.5">
                <label
                  htmlFor="recover-code"
                  className="text-sm font-medium text-foreground"
                >
                  Kode Pemulihan
                </label>
                <div className="relative">
                  <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                  <input
                    id="recover-code"
                    type="text"
                    required
                    placeholder="Masukkan kode pemulihan"
                    className={ICON_INPUT_CLASS}
                    value={recoverForm.recovery_code}
                    onChange={(e) =>
                      setRecoverForm((prev) => ({
                        ...prev,
                        recovery_code: e.target.value,
                      }))
                    }
                    aria-invalid={Boolean(fieldError(error, "recovery_code"))}
                    disabled={isLoading}
                  />
                </div>
                <FieldMessage message={fieldError(error, "recovery_code")} />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="recover-password"
                  className="text-sm font-medium text-foreground"
                >
                  Kata Sandi Baru
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
                  <input
                    id="recover-password"
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder="Minimal delapan karakter"
                    className={ICON_INPUT_CLASS}
                    value={recoverForm.new_password}
                    onChange={(e) =>
                      setRecoverForm((prev) => ({
                        ...prev,
                        new_password: e.target.value,
                      }))
                    }
                    aria-invalid={Boolean(fieldError(error, "new_password"))}
                    disabled={isLoading}
                  />
                </div>
                <FieldMessage message={fieldError(error, "new_password")} />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className={cn(
                  ACTION_CLASS,
                  "bg-navy text-white hover:bg-navy-light",
                )}
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  MODE_COPY.recover.submit
                )}
              </button>
            </form>
          )}

          <div className="mt-8 pt-6 border-t border-border text-center space-y-2">
            {mode === "login" ? (
              <p className="text-sm text-muted">
                Belum punya akun?{" "}
                <button
                  type="button"
                  onClick={() => switchMode("register")}
                  className="min-h-11 inline-flex items-center font-semibold text-navy hover:text-gold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy rounded cursor-pointer"
                >
                  Daftar akun
                </button>
              </p>
            ) : (
              <p className="text-sm text-muted">
                Sudah punya akun?{" "}
                <button
                  type="button"
                  onClick={() => switchMode("login")}
                  className="min-h-11 inline-flex items-center font-semibold text-navy hover:text-gold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy rounded cursor-pointer"
                >
                  Kembali ke masuk
                </button>
              </p>
            )}
            <p className="text-xs text-muted">
              © {CURRENT_YEAR} Fakultas Teknologi Maju dan Multidisiplin
              <br />
              Universitas Airlangga
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
