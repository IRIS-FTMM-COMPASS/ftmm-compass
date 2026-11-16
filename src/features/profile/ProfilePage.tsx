import EditProfileModal from "@/features/profile/components/EditProfileModal"
import ProfileBody from "@/features/profile/components/ProfileBody"
import ProfileHeader from "@/features/profile/components/ProfileHeader"
import { useProfileEditor } from "@/features/profile/hooks/useProfileEditor"
import { useAcademicPeriod } from "@/shared/academic-period/academic"

interface ProfileProps {
  onNavigate: (page: string) => void
  onRequestLogout: () => void
}

export default function Profile({ onNavigate, onRequestLogout }: ProfileProps) {
  const { period } = useAcademicPeriod()
  const editor = useProfileEditor()

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-in fade-in duration-300 pb-12">
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
