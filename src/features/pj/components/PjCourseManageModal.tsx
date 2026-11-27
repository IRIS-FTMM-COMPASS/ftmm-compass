import { useEffect, useMemo, useState, type FormEvent } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  Trash2,
  Users,
} from "lucide-react"
import ModalShell from "@/shared/ui/course/ModalShell"
import ProdiBadge from "@/shared/ui/ProdiBadge"
import SearchableCombobox, {
  type ComboboxOption,
} from "@/shared/ui/SearchableCombobox"
import { useDiscardGuard } from "@/shared/hooks/useDiscardGuard"
import { ApiError, apiErrorMessage } from "@/shared/api/client"
import { cn } from "@/shared/utils"
import {
  pjService,
  type PjAvailabilityItem,
} from "@/features/polling/pollingService"
import {
  schedulingService,
  type InstructorCandidateItem,
  type InstructorReferenceResponse,
} from "@/features/scheduling/schedulingService"

interface PjCourseManageModalProps {
  item: PjAvailabilityItem
  academicPeriodId: string
  studyProgram: string | null
  onClose: () => void
  onSaved: (item: PjAvailabilityItem) => void
}

interface QuotaFieldErrors {
  classCount?: string
  capacity?: string
}

const LOCK_REASON_LABELS: Record<string, string> = {
  semester_berjalan: "Semester berjalan — perubahan terkunci",
  bukan_pilihan: "Bukan MK Pilihan",
  dinonaktifkan: "MK sudah dinonaktifkan",
  prodi_lain: "Dikelola program studi lain",
}

function lockReasonLabel(reason: string | null | undefined): string {
  if (!reason) return ""
  return LOCK_REASON_LABELS[reason] ?? reason.replace(/_/g, " ")
}

const NAME_TITLES: Record<string, true> = {
  dr: true,
  ir: true,
  prof: true,
  drs: true,
  dra: true,
  eng: true,
  hj: true,
  h: true,
  cand: true,
  sp: true,
  btkv: true,
  k: true,
}

/** Samakan aturan backend: buang gelar setelah koma pertama, kecilkan, dan sisakan kata bermakna. */
function normalizeInstructorName(raw: string | null | undefined): string {
  if (!raw) return ""
  const head = raw.split(",", 1)[0]?.toLowerCase() ?? ""
  return head
    .replace(/[^a-z]+/g, " ")
    .split(" ")
    .filter((token) => token.length > 1 && !NAME_TITLES[token])
    .join(" ")
}

const PJMK_TEAM_MESSAGE =
  "PJMK sudah mengajar mata kuliah ini dan tidak dapat menjadi anggota tim pengajar."

const TEAM_MEMBER_MESSAGE =
  "Anggota tim pengajar tersebut sudah terdaftar pada mata kuliah ini."

const inputClass =
  "h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/40 disabled:cursor-not-allowed disabled:opacity-60"

export default function PjCourseManageModal({
  item,
  academicPeriodId,
  studyProgram,
  onClose,
  onSaved,
}: PjCourseManageModalProps) {
  const isReadOnly = item.lock_reason === "prodi_lain"
  const statusLocked = !item.can_toggle
  const statusReason = lockReasonLabel(item.lock_reason)

  const initialClassCount = item.class_count ?? 1
  const initialCapacity = item.capacity_per_class ?? 40

  const [classCount, setClassCount] = useState(String(initialClassCount))
  const [capacity, setCapacity] = useState(String(initialCapacity))
  const [isActive, setIsActive] = useState(item.is_active)
  const [reason, setReason] = useState("")
  const [fieldErrors, setFieldErrors] = useState<QuotaFieldErrors>({})
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const [team, setTeam] = useState<InstructorReferenceResponse[]>([])
  const [pjmk, setPjmk] = useState<InstructorReferenceResponse | null>(null)
  const [teamLoading, setTeamLoading] = useState(true)
  const [teamError, setTeamError] = useState<string | null>(null)
  const [teamReloadKey, setTeamReloadKey] = useState(0)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<Record<string, string | null>>(
    {},
  )

  const [candidates, setCandidates] = useState<InstructorCandidateItem[]>([])
  const [candidatesLoading, setCandidatesLoading] = useState(true)
  const [candidatesError, setCandidatesError] = useState<string | null>(null)
  const [selectedUserId, setSelectedUserId] = useState("")
  const [instructorName, setInstructorName] = useState("")
  const [isAdding, setIsAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const dirty =
    classCount !== String(initialClassCount) ||
    capacity !== String(initialCapacity) ||
    isActive !== item.is_active ||
    reason.trim() !== ""

  const { requestClose, discardDialog } = useDiscardGuard({
    dirty: dirty && !isSaving,
    onClose,
  })

  useEffect(() => {
    let active = true
    if (!academicPeriodId) {
      setTeamLoading(false)
      setTeamError("Periode akademik tidak tersedia.")
      return () => {
        active = false
      }
    }
    setTeamLoading(true)
    setTeamError(null)
    schedulingService
      .listInstructorReferences({ academic_period_id: academicPeriodId })
      .then((references) => {
        if (!active) return
        const courseReferences = references.filter(
          (reference) =>
            reference.curriculum_course_id === item.curriculum_course_id,
        )
        setTeam(
          courseReferences.filter(
            (reference) => reference.instructor_role === "teaching_team",
          ),
        )
        setPjmk(
          courseReferences.find(
            (reference) => reference.instructor_role === "pjmk",
          ) ?? null,
        )
      })
      .catch((cause) => {
        if (!active) return
        setTeamError(
          apiErrorMessage(cause, "Daftar tim pengajar tidak dapat dimuat."),
        )
      })
      .finally(() => {
        if (active) setTeamLoading(false)
      })
    return () => {
      active = false
    }
  }, [academicPeriodId, item.curriculum_course_id, teamReloadKey])

  useEffect(() => {
    let active = true
    if (!academicPeriodId) {
      setCandidatesLoading(false)
      setCandidatesError("Periode akademik tidak tersedia.")
      return () => {
        active = false
      }
    }
    setCandidatesLoading(true)
    setCandidatesError(null)
    schedulingService
      .listInstructorCandidates({
        academic_period_id: academicPeriodId,
        page: 1,
        page_size: 100,
      })
      .then((items) => {
        if (!active) return
        setCandidates(items.filter((candidate) => candidate.is_active))
      })
      .catch((cause) => {
        if (!active) return
        setCandidates([])
        setCandidatesError(
          apiErrorMessage(cause, "Daftar akun dosen tidak dapat dimuat."),
        )
      })
      .finally(() => {
        if (active) setCandidatesLoading(false)
      })
    return () => {
      active = false
    }
  }, [academicPeriodId])

  const totalQuota = useMemo(() => {
    const count = Number(classCount)
    const size = Number(capacity)
    if (!Number.isFinite(count) || !Number.isFinite(size)) return null
    return count * size
  }, [classCount, capacity])

  const pjmkName = pjmk ? (pjmk.lecturer_name ?? pjmk.instructor_name) : null
  const pjmkProdiCode = pjmk?.study_program_code ?? studyProgram

  /** Akun yang sudah mengajar MK ini: PJMK dan anggota tim yang ada. */
  const blockedAccounts = useMemo(() => {
    const userIds = new Set<string>()
    const names = new Set<string>()
    const addReference = (reference: InstructorReferenceResponse) => {
      if (reference.user_id) userIds.add(reference.user_id)
      for (const value of [
        reference.instructor_name,
        reference.lecturer_name,
      ]) {
        const normalized = normalizeInstructorName(value)
        if (normalized) names.add(normalized)
      }
    }
    if (pjmk) addReference(pjmk)
    team.forEach(addReference)
    return { userIds, names }
  }, [pjmk, team])

  const candidateOptions = useMemo<ComboboxOption[]>(
    () =>
      candidates
        .filter((candidate) => {
          if (blockedAccounts.userIds.has(candidate.user_id)) return false
          const normalized = normalizeInstructorName(candidate.full_name)
          return !normalized || !blockedAccounts.names.has(normalized)
        })
        .map((candidate) => ({
          value: candidate.user_id,
          label: candidate.full_name,
          hint: candidate.email,
        })),
    [blockedAccounts, candidates],
  )

  const accountOptions = useMemo<ComboboxOption[]>(
    () => [
      { value: "", label: "Dosen eksternal / tanpa akun" },
      ...candidateOptions,
    ],
    [candidateOptions],
  )

  const duplicateMessage = (userId: string, name: string): string | null => {
    const normalized = normalizeInstructorName(name)
    if (pjmk) {
      const samePjmkUser = Boolean(userId) && userId === pjmk.user_id
      const pjmkNames = [pjmk.instructor_name, pjmk.lecturer_name]
        .map(normalizeInstructorName)
        .filter(Boolean)
      const samePjmkName = Boolean(normalized) && pjmkNames.includes(normalized)
      if (samePjmkUser || samePjmkName) return PJMK_TEAM_MESSAGE
    }
    const inTeam = team.some((member) => {
      const sameUser = Boolean(userId) && userId === member.user_id
      const memberNames = [member.instructor_name, member.lecturer_name]
        .map(normalizeInstructorName)
        .filter(Boolean)
      const sameName = Boolean(normalized) && memberNames.includes(normalized)
      return sameUser || sameName
    })
    return inTeam ? TEAM_MEMBER_MESSAGE : null
  }

  const handleSave = async () => {
    if (isReadOnly || isSaving) return

    const count = Number(classCount)
    const size = Number(capacity)
    const errors: QuotaFieldErrors = {}
    if (!Number.isInteger(count) || count < 1 || count > 3) {
      errors.classCount = "Jumlah kelas harus berupa angka antara 1 dan 3."
    }
    if (!Number.isInteger(size) || size < 1 || size > 100) {
      errors.capacity =
        "Kapasitas per kelas harus berupa angka antara 1 dan 100."
    }
    setFieldErrors(errors)
    if (errors.classCount || errors.capacity) return

    setIsSaving(true)
    setSaveError(null)
    try {
      const quota = await pjService.setQuota(item.curriculum_course_id, {
        class_count: count,
        capacity_per_class: size,
      })

      let merged: PjAvailabilityItem = {
        ...item,
        class_count: quota.class_count,
        capacity_per_class: quota.capacity_per_class,
        total_quota: quota.total_quota,
        enrolled_count: quota.enrolled_count,
      }

      if (isActive !== item.is_active) {
        const availability = await pjService.setAvailability(
          item.curriculum_course_id,
          isActive,
          reason.trim() || undefined,
        )
        merged = {
          ...availability,
          class_count: quota.class_count,
          capacity_per_class: quota.capacity_per_class,
          total_quota: quota.total_quota,
          enrolled_count: quota.enrolled_count,
        }
      }

      onSaved(merged)
      onClose()
    } catch (cause) {
      setSaveError(apiErrorMessage(cause, "Perubahan gagal disimpan."))
    } finally {
      setIsSaving(false)
    }
  }

  const handleCandidateChange = (userId: string) => {
    setSelectedUserId(userId)
    const selected = candidates.find(
      (candidate) => candidate.user_id === userId,
    )
    setInstructorName(selected?.full_name ?? "")
    setAddError(null)
  }

  const handleAddInstructor = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isReadOnly || isAdding || !academicPeriodId) return
    const name = instructorName.trim()
    if (!name) {
      setAddError("Nama pengajar wajib diisi.")
      return
    }
    const duplicate = duplicateMessage(selectedUserId, name)
    if (duplicate) {
      setAddError(duplicate)
      return
    }
    setIsAdding(true)
    setAddError(null)
    try {
      const created = await schedulingService.createInstructorReference({
        curriculum_course_id: item.curriculum_course_id,
        academic_period_id: academicPeriodId,
        instructor_name: name,
        instructor_role: "teaching_team",
        ...(selectedUserId ? { user_id: selectedUserId } : {}),
      })
      setTeam((previous) => [...previous, created])
      setSelectedUserId("")
      setInstructorName("")
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        const code = cause.code
        const message = cause.message
        if (code === "pjmk_is_team" || /pjmk/i.test(message)) {
          setAddError(PJMK_TEAM_MESSAGE)
        } else if (
          code === "team_member_exists" ||
          /terdaftar/i.test(message)
        ) {
          setAddError(TEAM_MEMBER_MESSAGE)
        } else {
          setAddError(message)
        }
      } else {
        setAddError(
          apiErrorMessage(cause, "Pengajar gagal ditambahkan ke tim."),
        )
      }
    } finally {
      setIsAdding(false)
    }
  }

  const handleRemoveInstructor = async (
    reference: InstructorReferenceResponse,
  ) => {
    if (
      isReadOnly ||
      deletingId === reference.reference_id ||
      !academicPeriodId
    )
      return
    setDeletingId(reference.reference_id)
    setDeleteError((previous) => ({
      ...previous,
      [reference.reference_id]: null,
    }))
    try {
      await schedulingService.deleteInstructorReference(
        reference.reference_id,
        academicPeriodId,
      )
      setTeam((previous) =>
        previous.filter(
          (entry) => entry.reference_id !== reference.reference_id,
        ),
      )
    } catch (cause) {
      setDeleteError((previous) => ({
        ...previous,
        [reference.reference_id]: apiErrorMessage(
          cause,
          "Pengajar gagal dihapus dari tim.",
        ),
      }))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <>
      <ModalShell
        onClose={requestClose}
        labelledBy="pj-manage-modal-title"
        panelClassName="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-border bg-surface shadow-xl"
      >
        <div className="space-y-6 p-5 md:p-6">
          <header className="flex flex-col gap-2 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-mono text-xs font-bold uppercase tracking-wider text-gold">
                {item.course_code}
              </p>
              <h2
                id="pj-manage-modal-title"
                className="font-heading text-lg font-bold text-navy"
              >
                {item.course_name}
              </h2>
              <p className="text-xs text-muted">
                {studyProgram ?? "Program Studi"} · Semester{" "}
                {item.semester ?? "—"} · {item.credits} SKS
              </p>
            </div>
            <span
              className={cn(
                "inline-flex items-center gap-1 self-start whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider",
                item.is_active
                  ? "border-gold/40 bg-gold/15 text-navy"
                  : "border-border bg-secondary text-muted",
              )}
            >
              {item.is_active ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <Lock className="h-3 w-3" />
              )}
              {item.is_active ? "Aktif" : "Nonaktif"}
            </span>
          </header>

          {isReadOnly && (
            <div
              role="status"
              className="flex items-start gap-2 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-navy"
            >
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-orange" />
              <p>
                {statusReason || "Mata kuliah ini dikelola program studi lain."}{" "}
                Perubahan kuota, status, dan tim pengajar hanya dapat dilakukan
                oleh PJ program studi pemilik mata kuliah.
              </p>
            </div>
          )}

          <section
            aria-labelledby="pj-manage-quota-title"
            className="space-y-4"
          >
            <div>
              <h3
                id="pj-manage-quota-title"
                className="font-heading text-sm font-bold text-navy"
              >
                Kuota &amp; Status
              </h3>
              <p className="text-xs text-muted">
                Atur jumlah kelas, kapasitas, dan ketersediaan MK pada periode
                polling berikutnya.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="pj-manage-class-count"
                  className="mb-1 block text-xs font-semibold text-foreground"
                >
                  Jumlah kelas
                </label>
                <input
                  id="pj-manage-class-count"
                  type="number"
                  min={1}
                  max={3}
                  step={1}
                  inputMode="numeric"
                  value={classCount}
                  disabled={isReadOnly || isSaving}
                  aria-invalid={Boolean(fieldErrors.classCount)}
                  aria-describedby={
                    fieldErrors.classCount
                      ? "pj-manage-class-count-error"
                      : undefined
                  }
                  onChange={(event) => {
                    setClassCount(event.target.value)
                    setFieldErrors((previous) => ({
                      ...previous,
                      classCount: undefined,
                    }))
                  }}
                  className={cn(
                    inputClass,
                    fieldErrors.classCount && "border-orange",
                  )}
                />
                {fieldErrors.classCount && (
                  <p
                    id="pj-manage-class-count-error"
                    role="alert"
                    className="mt-1 text-[11px] text-orange"
                  >
                    {fieldErrors.classCount}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="pj-manage-capacity"
                  className="mb-1 block text-xs font-semibold text-foreground"
                >
                  Kapasitas per kelas
                </label>
                <input
                  id="pj-manage-capacity"
                  type="number"
                  min={1}
                  max={100}
                  step={1}
                  inputMode="numeric"
                  value={capacity}
                  disabled={isReadOnly || isSaving}
                  aria-invalid={Boolean(fieldErrors.capacity)}
                  aria-describedby={
                    fieldErrors.capacity
                      ? "pj-manage-capacity-error"
                      : undefined
                  }
                  onChange={(event) => {
                    setCapacity(event.target.value)
                    setFieldErrors((previous) => ({
                      ...previous,
                      capacity: undefined,
                    }))
                  }}
                  className={cn(
                    inputClass,
                    fieldErrors.capacity && "border-orange",
                  )}
                />
                {fieldErrors.capacity && (
                  <p
                    id="pj-manage-capacity-error"
                    role="alert"
                    className="mt-1 text-[11px] text-orange"
                  >
                    {fieldErrors.capacity}
                  </p>
                )}
              </div>
            </div>

            <dl className="grid grid-cols-2 gap-3 rounded-xl border border-border bg-background px-4 py-3 text-xs sm:grid-cols-4">
              <div>
                <dt className="text-muted">Total kuota</dt>
                <dd className="font-mono font-bold text-navy">
                  {totalQuota ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Terdaftar</dt>
                <dd className="font-mono font-bold text-navy">
                  {item.enrolled_count ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Semester</dt>
                <dd className="font-mono font-bold text-navy">
                  {item.semester ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Cakupan</dt>
                <dd className="font-medium text-navy">
                  {item.course_scope === "program_studi"
                    ? "Program Studi"
                    : item.course_scope === "fakultas"
                      ? "Fakultas"
                      : "Universitas"}
                </dd>
              </div>
            </dl>

            <div className="space-y-3 rounded-xl border border-border bg-background px-4 py-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-semibold text-foreground">
                    Ketersediaan MK
                  </p>
                  <p className="text-[11px] text-muted">
                    {statusLocked
                      ? statusReason ||
                        "Status tidak dapat diubah pada periode ini."
                      : "Nonaktifkan jika MK tidak ditawarkan pada periode berikutnya."}
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={isActive}
                  aria-label="Ketersediaan mata kuliah"
                  disabled={isReadOnly || statusLocked || isSaving}
                  onClick={() => {
                    setIsActive((previous) => !previous)
                    setSaveError(null)
                  }}
                  className={cn(
                    "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:ring-offset-2",
                    isActive
                      ? "border-gold/50 bg-gold"
                      : "border-border bg-secondary",
                    (isReadOnly || statusLocked || isSaving) &&
                      "cursor-not-allowed opacity-60",
                    !isReadOnly && !statusLocked && "cursor-pointer",
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      "inline-block h-5 w-5 transform rounded-full bg-surface shadow transition-transform",
                      isActive ? "translate-x-5" : "translate-x-0.5",
                    )}
                  />
                </button>
              </div>

              <div>
                <label
                  htmlFor="pj-manage-reason"
                  className="mb-1 block text-xs font-semibold text-foreground"
                >
                  Alasan perubahan status{" "}
                  <span className="font-normal text-muted">(opsional)</span>
                </label>
                <input
                  id="pj-manage-reason"
                  type="text"
                  value={reason}
                  disabled={isReadOnly || isSaving}
                  placeholder="Tuliskan alasan jika perlu"
                  onChange={(event) => setReason(event.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            {saveError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-orange"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {saveError}
              </div>
            )}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={requestClose}
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border px-4 text-xs font-semibold text-navy transition-colors hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 cursor-pointer"
              >
                Tutup
              </button>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={isReadOnly || isSaving}
                aria-disabled={isReadOnly || isSaving}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-navy bg-navy px-4 text-xs font-semibold text-surface transition-colors hover:bg-navy/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
              >
                {isSaving && (
                  <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
                )}
                {isSaving ? "Menyimpan..." : "Simpan"}
              </button>
            </div>
          </section>

          <section
            aria-labelledby="pj-manage-team-title"
            className="space-y-4 border-t border-border pt-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3
                  id="pj-manage-team-title"
                  className="flex items-center gap-2 font-heading text-sm font-bold text-navy"
                >
                  <Users aria-hidden className="h-4 w-4 text-gold" />
                  Tim Pengajar
                </h3>
                <p className="text-xs text-muted">
                  Dosen yang mengajar MK ini bersama PJMK. Perubahan langsung
                  tersimpan.
                </p>
              </div>
              <span className="rounded-full border border-border bg-background px-2 py-0.5 font-mono text-[10px] text-muted">
                {team.length} pengajar
              </span>
            </div>

            {pjmk && (
              <div className="rounded-xl border border-gold/40 bg-gold/10 px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p
                    className="min-w-0 truncate text-sm font-semibold text-foreground"
                    title={pjmkName ?? undefined}
                  >
                    {pjmkName}
                  </p>
                  <span className="inline-flex items-center rounded-full border border-gold/50 bg-gold/25 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-navy">
                    PJ MK
                  </span>
                  {pjmkProdiCode && <ProdiBadge code={pjmkProdiCode} />}
                </div>
                <p className="mt-1 text-[11px] text-muted">
                  PJMK sudah mengajar MK ini dan tidak termasuk dalam daftar tim
                  pengajar.
                </p>
              </div>
            )}

            {teamLoading && (
              <div className="flex items-center gap-2 rounded-xl border border-border bg-background px-4 py-6 text-xs text-muted">
                <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
                Memuat tim pengajar...
              </div>
            )}

            {!teamLoading && teamError && (
              <div
                role="alert"
                className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-navy sm:flex-row sm:items-center sm:justify-between"
              >
                <span className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 text-orange" />
                  {teamError}
                </span>
                <button
                  type="button"
                  onClick={() => setTeamReloadKey((key) => key + 1)}
                  className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border border-orange/40 px-3 text-[11px] font-semibold text-orange transition-colors hover:bg-orange/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 cursor-pointer"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Coba lagi
                </button>
              </div>
            )}

            {!teamLoading && !teamError && (
              <>
                {team.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-border bg-background px-4 py-6 text-center text-xs text-muted">
                    Belum ada pengajar pada tim MK ini.
                  </p>
                ) : (
                  <ul className="divide-y divide-border/60 rounded-xl border border-border bg-background">
                    {team.map((reference) => {
                      const isDeleting = deletingId === reference.reference_id
                      const error = deleteError[reference.reference_id]
                      return (
                        <li
                          key={reference.reference_id}
                          className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-foreground">
                              {reference.instructor_name}
                            </p>
                            <p className="text-[11px] text-muted">
                              {reference.is_mapped
                                ? "Terhubung dengan akun dosen"
                                : "Dosen eksternal — belum terhubung akun"}
                            </p>
                            {error && (
                              <p
                                role="alert"
                                className="mt-1 text-[11px] text-orange"
                              >
                                {error}
                              </p>
                            )}
                          </div>
                          <button
                            type="button"
                            disabled={isReadOnly || isDeleting}
                            aria-disabled={isReadOnly || isDeleting}
                            onClick={() =>
                              void handleRemoveInstructor(reference)
                            }
                            className="inline-flex min-h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-orange/40 px-3 text-[11px] font-semibold text-orange transition-colors hover:bg-orange/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
                          >
                            {isDeleting ? (
                              <Loader2
                                aria-hidden
                                className="h-3.5 w-3.5 animate-spin"
                              />
                            ) : (
                              <Trash2 aria-hidden className="h-3.5 w-3.5" />
                            )}
                            {isDeleting ? "Menghapus..." : "Hapus"}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}

                {!isReadOnly && (
                  <form
                    onSubmit={handleAddInstructor}
                    className="space-y-3 rounded-xl border border-border bg-background px-4 py-3"
                  >
                    <p className="text-xs font-semibold text-foreground">
                      Tambah pengajar
                    </p>
                    {candidatesError && (
                      <p role="alert" className="text-[11px] text-orange">
                        {candidatesError} Anda tetap dapat menuliskan nama dosen
                        secara manual.
                      </p>
                    )}
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <SearchableCombobox
                          id="pj-manage-instructor-account"
                          label="Akun dosen (opsional)"
                          options={accountOptions}
                          value={selectedUserId}
                          onChange={handleCandidateChange}
                          placeholder={
                            candidatesLoading
                              ? "Memuat akun dosen..."
                              : "Pilih akun atau dosen eksternal"
                          }
                          searchPlaceholder="Cari nama atau email dosen"
                          emptyLabel="Tidak ada akun dosen yang dapat ditambahkan."
                          disabled={candidatesLoading || isAdding}
                        />
                        <p className="mt-1 text-[11px] text-muted">
                          PJMK dan pengajar yang sudah ada tidak ditampilkan.
                        </p>
                      </div>
                      <div>
                        <label
                          htmlFor="pj-manage-instructor-name"
                          className="mb-1 block text-[11px] font-semibold text-foreground"
                        >
                          Nama pengajar
                        </label>
                        <input
                          id="pj-manage-instructor-name"
                          type="text"
                          value={instructorName}
                          disabled={isAdding}
                          placeholder="Nama lengkap dosen"
                          onChange={(event) => {
                            setInstructorName(event.target.value)
                            setSelectedUserId("")
                            setAddError(null)
                          }}
                          className={inputClass}
                        />
                      </div>
                    </div>
                    {addError && (
                      <p role="alert" className="text-[11px] text-orange">
                        {addError}
                      </p>
                    )}
                    <div className="flex justify-end">
                      <button
                        type="submit"
                        disabled={isAdding}
                        aria-disabled={isAdding}
                        className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border border-gold/40 bg-gold/15 px-4 text-xs font-semibold text-navy transition-colors hover:bg-gold/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
                      >
                        {isAdding ? (
                          <Loader2
                            aria-hidden
                            className="h-3.5 w-3.5 animate-spin"
                          />
                        ) : (
                          <Plus aria-hidden className="h-3.5 w-3.5" />
                        )}
                        {isAdding ? "Menambahkan..." : "Tambah pengajar"}
                      </button>
                    </div>
                  </form>
                )}
              </>
            )}
          </section>
        </div>
      </ModalShell>
      {discardDialog}
    </>
  )
}
