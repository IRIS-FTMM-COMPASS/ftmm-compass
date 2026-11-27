import { useEffect, useState } from "react"
import {
  authService,
  type AuthUser,
  type ProfileUpdatePayload,
} from "@/features/auth/authService"
import { useSession } from "@/features/auth/session"

const ROLE_LABEL_MAP: Record<string, string> = {
  student: "Mahasiswa Aktif",
  lecturer: "Dosen Pengajar",
  admin: "Administrator FTMM",
  faculty_staff: "Staf Fakultas",
}

export function useProfileEditor() {
  const { user: currentUser, setUser } = useSession()
  const [user, setLocalUser] = useState<AuthUser | null>(currentUser)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [refreshSuccess, setRefreshSuccess] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)

  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editPhone, setEditPhone] = useState(user?.phone_number || "")
  const [editBio, setEditBio] = useState(user?.bio || "")
  const [editInterests, setEditInterests] = useState(
    user?.career_interests?.join(", ") || "",
  )
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(
    null,
  )
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    setLocalUser(currentUser)
    setEditPhone(currentUser?.phone_number || "")
    setEditBio(currentUser?.bio || "")
    setEditInterests(currentUser?.career_interests?.join(", ") || "")
  }, [currentUser])

  const handleRefreshProfile = async () => {
    setIsRefreshing(true)
    setRefreshError(null)
    setRefreshSuccess(false)
    try {
      const freshUser = await authService.getMe()
      setLocalUser(freshUser)
      setUser(freshUser)
      setRefreshSuccess(true)
      setTimeout(() => setRefreshSuccess(false), 3000)
    } catch (err: unknown) {
      setRefreshError(
        err instanceof Error ? err.message : "Gagal memperbarui profil",
      )
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleOpenEditModal = () => {
    setEditPhone(user?.phone_number || "")
    setEditBio(user?.bio || "")
    setEditInterests(user?.career_interests?.join(", ") || "")
    setSaveErrorMessage(null)
    setSaveSuccessMessage(null)
    setIsEditModalOpen(true)
  }

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSavingProfile(true)
    setSaveErrorMessage(null)
    setSaveSuccessMessage(null)

    try {
      const interestsArray = editInterests
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)

      const payload: ProfileUpdatePayload = {
        phone_number: editPhone,
        bio: editBio,
        career_interests: interestsArray,
      }
      const updatedUser = await authService.updateProfile(payload)
      setLocalUser(updatedUser)
      setUser(updatedUser)
      setSaveSuccessMessage("Preferensi profil berhasil disimpan.")
      setTimeout(() => {
        setIsEditModalOpen(false)
        setSaveSuccessMessage(null)
      }, 1000)
    } catch (err: unknown) {
      setSaveErrorMessage(
        err instanceof Error
          ? err.message
          : "Gagal menyimpan perubahan profil.",
      )
    } finally {
      setIsSavingProfile(false)
    }
  }

  const roleLabel = user?.role
    ? user.role === "lecturer" && user.is_program_coordinator
      ? "PJ Prodi"
      : ROLE_LABEL_MAP[user.role] || user.role
    : "Mahasiswa Aktif"

  const studentProfile = user?.student_profile
  const academicId =
    user?.academic_identifier || studentProfile?.student_number || "—"

  return {
    user,
    roleLabel,
    academicId,
    studentProfile,
    isRefreshing,
    refreshSuccess,
    refreshError,
    handleRefreshProfile,
    isEditModalOpen,
    editPhone,
    setEditPhone,
    editBio,
    setEditBio,
    editInterests,
    setEditInterests,
    isSavingProfile,
    saveSuccessMessage,
    saveErrorMessage,
    handleOpenEditModal,
    closeEditModal: () => setIsEditModalOpen(false),
    handleSaveProfile,
  }
}
