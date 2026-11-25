import { useState, type FormEvent } from "react"
import { AlertCircle, Check, Lock } from "lucide-react"
import EditProfileModal from "@/features/profile/components/EditProfileModal"
import ProfileBody from "@/features/profile/components/ProfileBody"
import ProfileHeader from "@/features/profile/components/ProfileHeader"
import { useProfileEditor } from "@/features/profile/hooks/useProfileEditor"
import { useAcademicPeriod } from "@/shared/academic-period/academic"
import {
  authService,
  authErrorMessage,
  fieldError,
} from "@/features/auth/authService"
import { cn } from "@/shared/utils"

interface ProfileProps {
  onNavigate: (page: string) => void
  onRequestLogout: () => void
}

const INPUT_CLASS =
  "w-full min-h-11 rounded-xl border border-border bg-surface px-4 text-foreground placeholder:text-muted focus:border-gold focus:ring-1 focus:ring-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 transition-all disabled:opacity-70"

function FieldMessage({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p className="mt-1 text-xs text-orange" role="alert">
      {message}
    </p>
  )
}

function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    if (newPassword !== confirmPassword) {
      setError(new Error("Konfirmasi kata sandi baru tidak sama."))
      return
    }

    setIsSaving(true)
    try {
      await authService.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      setSuccess(true)
    } catch (err: unknown) {
      setError(err)
    } finally {
      setIsSaving(false)
    }
  }

  const generalError =
    error &&
    !fieldError(error, "current_password") &&
    !fieldError(error, "new_password")
      ? authErrorMessage(error, "Kata sandi gagal diperbarui.")
      : null

  return (
    <section
      aria-labelledby="change-password-title"
      className="rounded-2xl border border-border bg-surface p-5 md:p-6 shadow-xs"
    >
      <div className="flex items-start gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-gold/10 text-gold flex items-center justify-center flex-shrink-0">
          <Lock className="w-5 h-5" />
        </div>
        <div>
          <h3
            id="change-password-title"
            className="font-heading font-bold text-lg text-navy"
          >
            Ganti Kata Sandi
          </h3>
          <p className="text-xs text-muted mt-1">
            Perbarui kata sandi secara berkala. Sesi Anda tetap aktif setelah
            perubahan.
          </p>
        </div>
      </div>

      {generalError && (
        <div
          className="mb-4 flex items-start gap-2 rounded-xl border border-orange/30 bg-orange/10 p-3 text-sm text-orange"
          role="alert"
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{generalError}</span>
        </div>
      )}
      {success && (
        <div
          className="mb-4 flex items-start gap-2 rounded-xl border border-gold/30 bg-gold/10 p-3 text-sm text-navy"
          role="status"
        >
          <Check className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>Kata sandi berhasil diperbarui.</span>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        <div className="space-y-1.5">
          <label
            htmlFor="current-password"
            className="text-sm font-medium text-foreground"
          >
            Kata Sandi Saat Ini
          </label>
          <input
            id="current-password"
            type="password"
            required
            autoComplete="current-password"
            placeholder="Masukkan kata sandi saat ini"
            className={INPUT_CLASS}
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            aria-invalid={Boolean(fieldError(error, "current_password"))}
            disabled={isSaving}
          />
          <FieldMessage message={fieldError(error, "current_password")} />
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="new-password"
            className="text-sm font-medium text-foreground"
          >
            Kata Sandi Baru
          </label>
          <input
            id="new-password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            placeholder="Minimal delapan karakter"
            className={INPUT_CLASS}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            aria-invalid={Boolean(fieldError(error, "new_password"))}
            disabled={isSaving}
          />
          <FieldMessage message={fieldError(error, "new_password")} />
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="confirm-password"
            className="text-sm font-medium text-foreground"
          >
            Ulangi Kata Sandi Baru
          </label>
          <input
            id="confirm-password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            placeholder="Ulangi kata sandi baru"
            className={INPUT_CLASS}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={isSaving}
          />
        </div>

        <div className="md:col-span-3 flex justify-end">
          <button
            type="submit"
            disabled={isSaving}
            className={cn(
              "min-h-11 px-5 rounded-xl bg-navy text-white font-medium transition-all",
              "hover:bg-navy-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2",
              "disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer",
            )}
          >
            {isSaving ? "Menyimpan perubahan" : "Perbarui kata sandi"}
          </button>
        </div>
      </form>
    </section>
  )
}

export default function Profile({ onNavigate, onRequestLogout }: ProfileProps) {
  const { period } = useAcademicPeriod()
  const editor = useProfileEditor()

  return (
    <div
      className={cn(
        "space-y-6 w-full animate-in fade-in duration-300 pb-12",
        "[&_button:not(.group)]:min-h-11 [&_button:not(.group)]:min-w-11",
        "[&_button:not(.group)]:inline-flex [&_button:not(.group)]:items-center [&_button:not(.group)]:justify-center",
        "[&_input]:min-h-11 [&_select]:min-h-11 [&_textarea]:min-h-11",
      )}
    >
      <ProfileHeader
        user={editor.user}
        roleLabel={editor.roleLabel}
        academicId={editor.academicId}
        isRefreshing={editor.isRefreshing}
        refreshSuccess={editor.refreshSuccess}
        refreshError={editor.refreshError}
        onOpenEditModal={editor.handleOpenEditModal}
        onRefreshProfile={editor.handleRefreshProfile}
      />
      <ProfileBody
        user={editor.user}
        studentProfile={editor.studentProfile}
        academicId={editor.academicId}
        period={period}
        onNavigate={onNavigate}
        onRequestLogout={onRequestLogout}
        onEditPreferences={editor.handleOpenEditModal}
      />
      <ChangePasswordForm />
      <EditProfileModal
        isOpen={editor.isEditModalOpen}
        user={editor.user}
        academicId={editor.academicId}
        editPhone={editor.editPhone}
        onPhoneChange={editor.setEditPhone}
        editBio={editor.editBio}
        onBioChange={editor.setEditBio}
        editInterests={editor.editInterests}
        onInterestsChange={editor.setEditInterests}
        isSaving={editor.isSavingProfile}
        saveError={editor.saveErrorMessage}
        saveSuccess={editor.saveSuccessMessage}
        onClose={editor.closeEditModal}
        onSubmit={editor.handleSaveProfile}
      />
    </div>
  )
}
