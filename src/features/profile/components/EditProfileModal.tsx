import {
  Briefcase,
  Check,
  Edit3,
  FileText,
  Lock,
  Phone,
  ShieldCheck,
  X,
} from "lucide-react"
import type { AuthUser } from "@/features/auth/authService"

interface EditProfileModalProps {
  isOpen: boolean
  user: AuthUser | null
  academicId: string
  editPhone: string
  onPhoneChange: (value: string) => void
  editBio: string
  onBioChange: (value: string) => void
  editInterests: string
  onInterestsChange: (value: string) => void
  isSaving: boolean
  saveError: string | null
  saveSuccess: string | null
  onClose: () => void
  onSubmit: (event: React.FormEvent) => void
}

export default function EditProfileModal({
  isOpen,
  user,
  academicId,
  editPhone,
  onPhoneChange,
  editBio,
  onBioChange,
  editInterests,
  onInterestsChange,
  isSaving,
  saveError,
  saveSuccess,
  onClose,
  onSubmit,
}: EditProfileModalProps) {
  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-profile-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-surface rounded-2xl border border-border shadow-2xl max-w-lg w-full p-6 space-y-5 animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <Edit3 className="w-5 h-5 text-gold" />
            <h3
              id="edit-profile-title"
              className="font-heading font-bold text-lg text-navy"
            >
              Edit Preferensi Profil
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-muted hover:text-navy hover:bg-background transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {user?.role === "admin" ? (
          <div className="p-3.5 rounded-xl bg-teal/10 border border-teal/30 flex items-start gap-2.5 text-xs text-navy">
            <ShieldCheck className="w-4 h-4 text-teal flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-navy">
                Hak Akses Super Administrator
              </p>
              <p className="text-[11px] mt-0.5 text-muted">
                Akun memiliki wewenang penuh untuk mengelola katalog kurikulum,
                periode polling pra-KRS, dan konfigurasi operasional akademik
                fakultas.
              </p>
            </div>
          </div>
        ) : (
          <div className="p-3.5 rounded-xl bg-background border border-border flex items-start gap-2.5 text-xs text-muted">
            <Lock className="w-4 h-4 text-muted flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-navy">
                Data Identitas Akademik Terkunci
              </p>
              <p className="text-[11px] mt-0.5">
                NIM/NIP ({academicId}), Program Studi (
                {user?.unit_name || "FTMM"}), dan Hak Akses ({user?.role})
                dikelola terpusat oleh Cybercampus UNAIR dan tidak dapat diubah
                secara mandiri.
              </p>
            </div>
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label
              htmlFor="profile-phone"
              className="block text-xs font-semibold text-navy"
            >
              Nomor WhatsApp / Telepon
            </label>
            <div className="relative">
              <input
                id="profile-phone"
                type="tel"
                value={editPhone}
                onChange={(e) => onPhoneChange(e.target.value)}
                placeholder="Contoh: 081234567890"
                className="w-full h-10 px-3 pl-9 rounded-xl border border-border bg-background text-sm text-foreground focus:border-gold focus:ring-1 focus:ring-gold outline-hidden transition-colors"
              />
              <Phone className="w-4 h-4 text-muted absolute left-3 top-3 pointer-events-none" />
            </div>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="profile-bio"
              className="block text-xs font-semibold text-navy"
            >
              Bio Singkat / Catatan Akademik
            </label>
            <div className="relative">
              <textarea
                id="profile-bio"
                rows={3}
                value={editBio}
                onChange={(e) => onBioChange(e.target.value)}
                placeholder="Tuliskan catatan akademik atau profil singkat Anda..."
                className="w-full p-3 pl-9 rounded-xl border border-border bg-background text-sm text-foreground focus:border-gold focus:ring-1 focus:ring-gold outline-hidden transition-colors"
              />
              <FileText className="w-4 h-4 text-muted absolute left-3 top-3.5 pointer-events-none" />
            </div>
          </div>

          {user?.role === "student" && (
            <div className="space-y-1.5">
              <label
                htmlFor="profile-interests"
                className="block text-xs font-semibold text-navy"
              >
                Bidang Minat &amp; Karir (Pisahkan dengan koma)
              </label>
              <div className="relative">
                <input
                  id="profile-interests"
                  type="text"
                  value={editInterests}
                  onChange={(e) => onInterestsChange(e.target.value)}
                  placeholder="Contoh: Machine Learning, Data Science, Web Backend"
                  className="w-full h-10 px-3 pl-9 rounded-xl border border-border bg-background text-sm text-foreground focus:border-gold focus:ring-1 focus:ring-gold outline-hidden transition-colors"
                />
                <Briefcase className="w-4 h-4 text-muted absolute left-3 top-3 pointer-events-none" />
              </div>
              <p className="text-[11px] text-muted">
                Minat ini digunakan oleh Compass AI untuk merekomendasikan mata
                kuliah pilihan yang sesuai.
              </p>
            </div>
          )}

          {saveError && (
            <div className="p-3 rounded-lg bg-orange/10 border border-orange/30 text-orange text-xs">
              {saveError}
            </div>
          )}

          {saveSuccess && (
            <div className="p-3 rounded-lg bg-teal/10 border border-teal/30 text-navy-dark text-xs flex items-center gap-1.5">
              <Check className="w-4 h-4 text-teal" />
              <span>{saveSuccess}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="w-full py-2.5 px-4 rounded-xl border border-border bg-background hover:bg-surface text-foreground font-medium text-xs transition-colors cursor-pointer"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="w-full py-2.5 px-4 rounded-xl bg-navy hover:bg-navy-light text-white font-medium text-xs transition-colors cursor-pointer shadow-sm disabled:opacity-60"
            >
              {isSaving ? "Menyimpan..." : "Simpan Perubahan"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
