import {
  Building2,
  Check,
  CheckCircle2,
  Edit3,
  Mail,
  RefreshCw,
  Sparkles,
  User,
} from "lucide-react"
import type { AuthUser } from "@/features/auth/authService"

interface ProfileHeaderProps {
  user: AuthUser | null
  roleLabel: string
  academicId: string
  isRefreshing: boolean
  refreshSuccess: boolean
  refreshError: string | null
  onOpenEditModal: () => void
  onRefreshProfile: () => void
}

export default function ProfileHeader({
  user,
  roleLabel,
  academicId,
  isRefreshing,
  refreshSuccess,
  refreshError,
  onOpenEditModal,
  onRefreshProfile,
}: ProfileHeaderProps) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm p-6 md:p-8 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-80 h-80 bg-teal/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-1/3 w-64 h-64 bg-gold/5 rounded-full blur-3xl pointer-events-none" />

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
        <div className="flex items-start md:items-center gap-5">
          <div className="relative">
            <div className="w-20 h-20 md:w-24 md:h-24 rounded-2xl bg-gradient-to-br from-navy to-navy-light text-gold flex items-center justify-center font-heading font-bold text-3xl shadow-md border-2 border-gold/30">
              {user?.full_name ? (
                user.full_name
                  .split(" ")
                  .filter(Boolean)
                  .slice(0, 2)
                  .map((n) => n[0])
                  .join("")
                  .toUpperCase()
              ) : (
                <User className="w-10 h-10 text-gold" />
              )}
            </div>
            <span className="absolute -bottom-1 -right-1 p-1 bg-white rounded-full shadow-sm">
              <span className="flex h-3.5 w-3.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-teal"></span>
              </span>
            </span>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="text-2xl md:text-3xl font-heading font-bold text-navy">
                {user?.full_name || "Civitas Academica FTMM"}
              </h2>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gold/15 text-navy border border-gold/40">
                <Sparkles className="w-3 h-3 text-gold" />
                {roleLabel}
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-teal/15 text-navy-dark border border-teal/40">
                <CheckCircle2 className="w-3 h-3 text-teal" />
                Akun Terverifikasi
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
              <span className="font-mono text-navy font-medium bg-background px-2.5 py-0.5 rounded border border-border text-xs">
                {user?.role === "student" ? "NIM" : "NIP"}: {academicId}
              </span>
              <span className="flex items-center gap-1.5 text-xs">
                <Mail className="w-3.5 h-3.5 text-muted" />
                {user?.email || "Belum ada email"}
              </span>
              <span className="flex items-center gap-1.5 text-xs">
                <Building2 className="w-3.5 h-3.5 text-muted" />
                {user?.unit_name || "FTMM UNAIR"}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 self-start md:self-center">
          <button
            type="button"
            onClick={onOpenEditModal}
            title="Edit Preferensi Kontak & Minat"
            className="px-3.5 py-2 rounded-xl bg-gold/15 hover:bg-gold/25 text-navy border border-gold/40 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-xs"
          >
            <Edit3 className="w-3.5 h-3.5 text-navy" />
            <span>Edit Preferensi</span>
          </button>
          <button
            type="button"
            onClick={onRefreshProfile}
            disabled={isRefreshing}
            title="Sinkronisasi data profil terbaru dari Basis Data Lokal FTMM"
            className="px-3.5 py-2 rounded-xl border border-border bg-background hover:bg-surface text-navy text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer shadow-xs disabled:opacity-60"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`}
            />
            <span>{isRefreshing ? "Memperbarui..." : "Sinkronkan"}</span>
          </button>
        </div>
      </div>

      {refreshSuccess && (
        <div className="mt-4 p-3 rounded-xl bg-teal/10 border border-teal/30 text-navy-dark text-xs flex items-center gap-2">
          <Check className="w-4 h-4 text-teal" />
          <span>
            Data profil berhasil disinkronkan dengan basis data lokal FTMM.
          </span>
        </div>
      )}

      {refreshError && (
        <div className="mt-4 p-3 rounded-lg bg-orange/10 border border-orange/30 text-orange text-xs">
          {refreshError}
        </div>
      )}
    </div>
  )
}
