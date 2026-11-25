import { useEffect, useMemo, useRef, useState } from "react"
import { AlertCircle, Pin, RefreshCw, Save, Trash2 } from "lucide-react"
import { apiErrorMessage } from "@/shared/api/client"
import { useSession } from "@/features/auth/session"
import ConfirmDialog from "@/shared/ui/ConfirmDialog"
import SearchableCombobox from "@/shared/ui/SearchableCombobox"
import { cn } from "@/shared/utils"
import {
  schedulingService,
  type AssignmentDecision,
  type AssignmentPreviewClass,
  type AssignmentPreviewGroup,
  type AssignmentPreviewResponse,
  type EligibleCurriculumContext,
  type PreferencePeriod,
  type SchedulingProgramIdentity,
} from "../schedulingService"

const inputClass =
  "min-h-11 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
const buttonClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
const comboboxClass =
  "[&_button]:min-h-11 [&_input]:min-h-11 [&_[role=option]]:min-h-11"

interface DeleteTarget {
  group: AssignmentPreviewGroup
  item: AssignmentPreviewClass
}

type ContextSelections = Record<string, string>

interface AssignmentContextOption {
  curriculum_course_id: string
  course_code: string
  course_name: string
  programs: SchedulingProgramIdentity[]
}
interface AssignmentClassContext extends AssignmentContextOption {
  can_edit: boolean
}

interface AmbiguousAssignmentClass {
  class_section_id: string
  section_code: string
  contexts: AssignmentClassContext[]
}

function decisionsFromPreview(
  preview: AssignmentPreviewResponse,
  selections: ContextSelections,
): Record<string, AssignmentDecision> {
  const decisions: Record<string, AssignmentDecision> = {}
  for (const group of preview.data) {
    if (!group.can_edit) continue
    for (const item of group.classes) {
      if (
        !item.can_edit ||
        selections[item.class_section_id] !== group.curriculum_course_id
      ) {
        continue
      }
      const lecturer = item.existing_assignment ?? item.candidate
      if (!lecturer) continue
      decisions[item.class_section_id] = {
        class_section_id: item.class_section_id,
        curriculum_course_id: group.curriculum_course_id,
        user_id: lecturer.user_id,
        source: item.existing_assignment?.source ?? "auto",
        is_pinned: item.existing_assignment?.is_pinned ?? false,
      }
    }
  }
  return decisions
}

function selectionsFromPreview(
  preview: AssignmentPreviewResponse,
  current: ContextSelections,
  initialCurriculumCourseId: string | null,
): ContextSelections {
  const contextsByClass = new Map<string, Array<{
    curriculum_course_id: string
    can_edit: boolean
  }>>()
  for (const group of preview.data) {
    for (const item of group.classes) {
      const contexts = contextsByClass.get(item.class_section_id) ?? []
      contexts.push({
        curriculum_course_id: group.curriculum_course_id,
        can_edit: group.can_edit && item.can_edit,
      })
      contextsByClass.set(item.class_section_id, contexts)
    }
  }
  const selections: ContextSelections = {}
  for (const [classId, contexts] of contextsByClass) {
    const editableContexts = contexts.filter((context) => context.can_edit)
    const selectableContexts =
      editableContexts.length > 0 ? editableContexts : contexts
    const currentContext = selectableContexts.find(
      (context) => context.curriculum_course_id === current[classId],
    )
    const initialContext = selectableContexts.find(
      (context) => context.curriculum_course_id === initialCurriculumCourseId,
    )
    if (currentContext) {
      selections[classId] = currentContext.curriculum_course_id
    } else if (initialContext) {
      selections[classId] = initialContext.curriculum_course_id
    } else if (selectableContexts.length === 1) {
      selections[classId] = selectableContexts[0].curriculum_course_id
    }
  }
  return selections
}

function lecturerName(
  group: AssignmentPreviewGroup,
  item: AssignmentPreviewClass,
  userId: string,
): string {
  return (
    (item.existing_assignment?.user_id === userId
      ? item.existing_assignment.lecturer_name
      : group.pool.find((lecturer) => lecturer.user_id === userId)
          ?.lecturer_name) ?? "Dosen tidak ditemukan"
  )
}

export interface AssignmentPanelProps {
  initialAcademicPeriodId?: string | null
  initialCurriculumCourseId?: string | null
  curriculumContexts?: EligibleCurriculumContext[]
  bootstrapKey?: number
}

export default function AssignmentPanel({
  initialAcademicPeriodId = null,
  initialCurriculumCourseId = null,
  curriculumContexts = [],
  bootstrapKey = 0,
}: AssignmentPanelProps) {
  const { user } = useSession()
  const canManage =
    user?.role === "admin" ||
    (user?.role === "lecturer" && user.is_program_coordinator === true)
  const [periods, setPeriods] = useState<PreferencePeriod[]>([])
  const [periodId, setPeriodId] = useState("")
  const [periodsLoading, setPeriodsLoading] = useState(true)
  const [periodsError, setPeriodsError] = useState<string | null>(null)
  const [periodReloadKey, setPeriodReloadKey] = useState(0)
  const [contextFilter, setContextFilter] = useState(
    initialCurriculumCourseId ?? "",
  )
  const [selectedContexts, setSelectedContexts] = useState<ContextSelections>(
    {},
  )
  const selectedContextsRef = useRef<ContextSelections>({})
  const [preview, setPreview] = useState<AssignmentPreviewResponse | null>(null)
  const [decisions, setDecisions] =
    useState<Record<string, AssignmentDecision>>({})
  const [savedDecisions, setSavedDecisions] =
    useState<Record<string, AssignmentDecision>>({})
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const requestSequence = useRef(0)
  const consumedBootstrapKey = useRef(0)

  useEffect(() => {
    if (!canManage) return
    let active = true
    setPeriodsLoading(true)
    setPeriodsError(null)
    schedulingService
      .listPreferencePeriods()
      .then((response) => {
        if (!active) return
        setPeriods(response.data)
        setPeriodId((current) => {
          const requestedPeriod = response.data.some(
            (period) => period.academic_period_id === initialAcademicPeriodId,
          )
            ? initialAcademicPeriodId
            : null
          return (
            requestedPeriod ||
            current ||
            response.meta.current_academic_period_id ||
            response.data[0]?.academic_period_id ||
            ""
          )
        })
      })
      .catch((cause) => {
        if (active)
          setPeriodsError(
            apiErrorMessage(
              cause,
              "Daftar periode akademik tidak dapat dimuat.",
            ),
          )
      })
      .finally(() => {
        if (active) setPeriodsLoading(false)
      })
    return () => {
      active = false
    }
  }, [canManage, periodReloadKey, initialAcademicPeriodId])

  const applyPreview = (response: AssignmentPreviewResponse) => {
    const selections = selectionsFromPreview(
      response,
      selectedContextsRef.current,
      initialCurriculumCourseId,
    )
    selectedContextsRef.current = selections
    setSelectedContexts(selections)
    const next = decisionsFromPreview(response, selections)
    setPreview(response)
    setDecisions(next)
    setSavedDecisions(next)
  }

  const resetPreviewState = () => {
    requestSequence.current += 1
    selectedContextsRef.current = {}
    setSelectedContexts({})
    setPreview(null)
    setDecisions({})
    setSavedDecisions({})
    setLoadError(null)
    setSaveError(null)
    setNotice(null)
    setLoading(false)
  }

  const loadPreview = async (options?: {
    preserveNotice?: boolean
    curriculumCourseId?: string | null
  }) => {
    if (!periodId) return
    const sequence = ++requestSequence.current
    setLoading(true)
    setLoadError(null)
    setSaveError(null)
    if (!options?.preserveNotice) setNotice(null)
    try {
      const response = await schedulingService.previewAssignments(
        periodId,
        options?.curriculumCourseId !== undefined
          ? options.curriculumCourseId
          : contextFilter || null,
      )
      if (sequence !== requestSequence.current) return
      applyPreview(response)
    } catch (cause) {
      if (sequence !== requestSequence.current) return
      setPreview(null)
      setDecisions({})
      setLoadError(
        apiErrorMessage(
          cause,
          "Preview assignment pengajar tidak dapat dimuat.",
        ),
      )
    } finally {
      if (sequence === requestSequence.current) setLoading(false)
    }
  }

  const changePeriod = (nextPeriodId: string) => {
    setPeriodId(nextPeriodId)
    setContextFilter("")
    resetPreviewState()
  }

  const changeContextFilter = (nextCurriculumCourseId: string) => {
    if (dirty) return
    setContextFilter(nextCurriculumCourseId)
    resetPreviewState()
  }

  const chooseContext = (
    classSectionId: string,
    curriculumCourseId: string,
  ) => {
    if (!preview || dirty) return
    const next = {
      ...selectedContextsRef.current,
      [classSectionId]: curriculumCourseId,
    }
    selectedContextsRef.current = next
    setSelectedContexts(next)
    const decisions = decisionsFromPreview(preview, next)
    setDecisions(decisions)
    setSavedDecisions(decisions)
    setSaveError(null)
  }

  const updateDecision = (
    group: AssignmentPreviewGroup,
    item: AssignmentPreviewClass,
    patch: Partial<Pick<AssignmentDecision, "user_id" | "source" | "is_pinned">>,
  ) => {
    if (
      !group.can_edit ||
      !item.can_edit ||
      selectedContextsRef.current[item.class_section_id] !==
        group.curriculum_course_id
    ) {
      return
    }
    const current = decisions[item.class_section_id]
    if (!current) return
    setSaveError(null)
    setDecisions((previous) => ({
      ...previous,
      [item.class_section_id]: {
        ...current,
        ...patch,
        ...(patch.user_id && patch.user_id !== current.user_id
          ? { source: "manual" as const, is_pinned: false }
          : {}),
      },
    }))
  }

  const dirty = useMemo(
    () => JSON.stringify(decisions) !== JSON.stringify(savedDecisions),
    [decisions, savedDecisions],
  )
  const contextOptions = useMemo(() => {
    const byId = new Map<string, AssignmentContextOption>()
    for (const context of curriculumContexts) {
      byId.set(context.curriculum_course_id, {
        curriculum_course_id: context.curriculum_course_id,
        course_code: context.course_code,
        course_name: context.course_name,
        programs: [context],
      })
    }
    for (const group of preview?.data ?? []) {
      byId.set(group.curriculum_course_id, {
        curriculum_course_id: group.curriculum_course_id,
        course_code: group.course_code,
        course_name: group.course_name,
        programs: group.programs,
      })
    }
    return [...byId.values()].sort((a, b) =>
      `${a.programs[0]?.study_program_code ?? ""} ${a.course_code}`.localeCompare(
        `${b.programs[0]?.study_program_code ?? ""} ${b.course_code}`,
      ),
    )
  }, [curriculumContexts, preview])
  const ambiguousClasses = useMemo(() => {
    const byClass = new Map<string, AmbiguousAssignmentClass>()
    for (const group of preview?.data ?? []) {
      for (const item of group.classes) {
        const entry: AmbiguousAssignmentClass = byClass.get(
          item.class_section_id,
        ) ?? {
          class_section_id: item.class_section_id,
          section_code: item.section_code,
          contexts: [],
        }
        entry.contexts.push({
          curriculum_course_id: group.curriculum_course_id,
          course_code: group.course_code,
          course_name: group.course_name,
          programs: group.programs,
          can_edit: group.can_edit && item.can_edit,
        })
        byClass.set(item.class_section_id, entry)
      }
    }
    return [...byClass.values()].filter((entry) => entry.contexts.length > 1)
  }, [preview])
  const missingContextCount = ambiguousClasses.filter((entry) => {
    if (!entry.contexts.some((context) => context.can_edit)) return false
    const selectedContext = entry.contexts.find(
      (context) =>
        context.curriculum_course_id ===
        selectedContexts[entry.class_section_id],
    )
    return !selectedContext || !selectedContext.can_edit
  }).length
  const decisionCount = Object.keys(decisions).length
  const classCount = new Set(
    preview?.data.flatMap((group) =>
      group.classes.map((item) => item.class_section_id),
    ) ?? [],
  ).size

  useEffect(() => {
    if (
      !canManage ||
      bootstrapKey === 0 ||
      consumedBootstrapKey.current === bootstrapKey ||
      periodsLoading ||
      periodsError ||
      !periodId ||
      (initialAcademicPeriodId !== null && periodId !== initialAcademicPeriodId)
    ) {
      return
    }
    consumedBootstrapKey.current = bootstrapKey
    setContextFilter(initialCurriculumCourseId ?? "")
    resetPreviewState()
    void loadPreview({
      curriculumCourseId: initialCurriculumCourseId || null,
      preserveNotice: true,
    })
  }, [
    bootstrapKey,
    canManage,
    initialAcademicPeriodId,
    periodId,
    periodsError,
    periodsLoading,
  ])

  const save = async () => {
    if (!preview || !dirty || saving || missingContextCount > 0) return
    setSaving(true)
    setSaveError(null)
    try {
      await schedulingService.saveAssignments({
        decisions: Object.values(decisions),
      })
      setNotice("Assignment pengajar tersimpan.")
      await loadPreview({ preserveNotice: true })
    } catch (cause) {
      setSaveError(
        apiErrorMessage(cause, "Assignment pengajar gagal disimpan."),
      )
    } finally {
      setSaving(false)
    }
  }

  const removeAssignment = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await schedulingService.deleteAssignment(
        deleteTarget.item.class_section_id,
        deleteTarget.group.curriculum_course_id,
      )
      setDeleteTarget(null)
      setNotice("Assignment pengajar dihapus. Calon baru tampil pada preview.")
      await loadPreview({ preserveNotice: true })
    } catch (cause) {
      setDeleteError(
        apiErrorMessage(cause, "Assignment pengajar gagal dihapus."),
      )
    } finally {
      setDeleting(false)
    }
  }

  if (!canManage) return null

  return (
    <section aria-labelledby="assignment-title" className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <h2
            id="assignment-title"
            className="font-heading text-lg font-bold text-navy"
          >
            Penugasan Kelas
          </h2>
          <p className="max-w-2xl text-sm text-muted">
            Tinjau calon dosen, ubah pilihan, lalu simpan. Preview tidak
            menyimpan assignment dan tidak mengubah jadwal.
          </p>
          <p className="text-xs text-muted">
            {user?.role === "admin"
              ? "Cakupan admin: seluruh program studi."
              : "Cakupan PJ Prodi: program studi sesuai sesi Anda."}
          </p>
        </div>
        <label className="flex w-full flex-col gap-1 text-xs font-semibold text-navy lg:w-80">
          Periode akademik
          <select
            value={periodId}
            disabled={periodsLoading || saving || deleting}
            onChange={(event) => changePeriod(event.target.value)}
            className={inputClass}
          >
            {periods.map((period) => (
              <option
                key={period.academic_period_id}
                value={period.academic_period_id}
              >
                {period.label}
                {period.is_current ? " (aktif)" : ""}
              </option>
            ))}
          </select>
        </label>
        {(contextOptions.length > 1 || contextFilter) && (
          <div className="flex w-full flex-col gap-1 lg:w-80">
            <SearchableCombobox
              id="assignment-context-filter"
              label="Konteks kurikulum"
              options={[
                { value: "", label: "Semua konteks kurikulum" },
                ...contextOptions.map((context) => ({
                  value: context.curriculum_course_id,
                  label: `${context.programs
                    .map((program) => program.study_program_code)
                    .join(", ")} ${context.course_code} ${context.course_name}`,
                })),
              ]}
              value={contextFilter}
              disabled={periodsLoading || saving || deleting || dirty}
              onChange={changeContextFilter}
              placeholder="Semua konteks kurikulum"
              searchPlaceholder="Cari kode, nama, atau prodi"
              emptyLabel="Konteks kurikulum tidak ditemukan."
              className={comboboxClass}
              describeBy="assignment-context-filter-help"
            />
            {dirty && (
              <span
                id="assignment-context-filter-help"
                className="text-xs font-normal text-muted"
              >
                Muat ulang preview sebelum mengganti konteks.
              </span>
            )}
          </div>
        )}
      </div>

      {periodsLoading && (
        <p
          role="status"
          className="rounded-xl border border-border bg-surface p-6 text-sm text-muted"
        >
          Memuat periode akademik...
        </p>
      )}
      {!periodsLoading && periodsError && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-orange/30 bg-orange/10 p-4"
        >
          <span className="text-sm text-navy">{periodsError}</span>
          <button
            type="button"
            onClick={() => setPeriodReloadKey((key) => key + 1)}
            className={cn(
              buttonClass,
              "border border-orange bg-surface text-orange",
            )}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> Coba lagi
          </button>
        </div>
      )}
      {!periodsLoading && !periodsError && periods.length === 0 && (
        <p className="rounded-xl border border-border bg-surface p-6 text-sm text-muted">
          Belum ada periode akademik. Admin perlu menyiapkan periode terlebih
          dahulu.
        </p>
      )}

      {!periodsLoading && !periodsError && periodId && (
        <>
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted">
              Pilih konteks kurikulum bila tersedia, lalu muat preview. Pool
              menampilkan urutan gabungan Tim Pengajar untuk konteks tersebut.
            </p>
            <button
              type="button"
              onClick={() => void loadPreview()}
              disabled={loading || saving || deleting}
              className={cn(
                buttonClass,
                "border border-navy bg-navy text-white hover:bg-navy-light",
              )}
              aria-busy={loading}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              {loading
                ? "Memuat preview..."
                : preview
                  ? "Muat ulang preview"
                  : "Muat preview"}
            </button>
          </div>

          {notice && (
            <p
              role="status"
              className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-3 text-sm text-navy"
            >
              {notice}
            </p>
          )}
          {loading && (
            <p
              role="status"
              className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-muted"
            >
              Menghitung calon assignment untuk periode ini...
            </p>
          )}
          {!loading && loadError && (
            <div
              role="alert"
              className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="flex items-center gap-2 text-sm text-navy">
                <AlertCircle
                  className="h-4 w-4 shrink-0 text-orange"
                  aria-hidden="true"
                />
                {loadError}
              </span>
              <button
                type="button"
                onClick={() => void loadPreview()}
                className={cn(
                  buttonClass,
                  "border border-orange bg-surface text-orange",
                )}
              >
                Coba lagi
              </button>
            </div>
          )}
          {!loading && !loadError && !preview && (
            <div className="rounded-xl border border-border bg-surface p-8 text-center">
              <p className="font-semibold text-navy">Preview belum dimuat</p>
              <p className="mt-1 text-sm text-muted">
                Pilih periode, lalu tekan Muat preview untuk melihat calon dosen
                per kelas.
              </p>
            </div>
          )}
          {!loading && !loadError && preview && preview.data.length === 0 && (
            <div className="rounded-xl border border-border bg-surface p-8 text-center">
              <p className="font-semibold text-navy">
                {contextFilter
                  ? "Tidak ada kelas pada konteks kurikulum ini"
                  : "Belum ada kelas untuk dipreview"}
              </p>
              <p className="mt-1 text-sm text-muted">
                {contextFilter
                  ? "Pilih konteks lain atau muat semua konteks kurikulum."
                  : "Lengkapi pemetaan PJ MK dan Tim Pengajar, lalu muat preview kembali."}
              </p>
            </div>
          )}

          {!loading && !loadError && preview && preview.data.length > 0 && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted">
                <p>
                  {classCount} kelas, {decisionCount} calon assignment, revision{" "}
                  {preview.meta.input_revision}
                </p>
                <p
                  className={cn(dirty && "font-semibold text-orange")}
                  role="status"
                >
                  {dirty
                    ? "Ada perubahan yang belum disimpan"
                    : "Sesuai preview terakhir"}
                </p>
              </div>
              {ambiguousClasses.length > 0 && (
                <section
                  aria-labelledby="assignment-context-title"
                  className="space-y-3 rounded-xl border border-gold/40 bg-gold/10 p-4"
                >
                  <div>
                    <h3
                      id="assignment-context-title"
                      className="font-heading text-base font-bold text-navy"
                    >
                      Pilih konteks kurikulum
                    </h3>
                    <p className="mt-1 text-sm text-muted">
                      Kelas lintas prodi memiliki lebih dari satu konteks. Pilih
                      konteks sebelum mengubah atau menyimpan assignment.
                    </p>
                  </div>
                  <ul className="space-y-3">
                    {ambiguousClasses.map((entry) => (
                      <li key={entry.class_section_id}>
                        <label
                          htmlFor={`assignment-context-${entry.class_section_id}`}
                          className="flex flex-col gap-1 text-sm font-semibold text-navy"
                        >
                          Kelas {entry.section_code}
                          <select
                            id={`assignment-context-${entry.class_section_id}`}
                            value={
                              selectedContexts[entry.class_section_id] ?? ""
                            }
                            disabled={dirty || saving || deleting}
                            onChange={(event) =>
                              chooseContext(
                                entry.class_section_id,
                                event.target.value,
                              )
                            }
                            className={inputClass}
                          >
                            <option value="">Pilih konteks kurikulum</option>
                            {entry.contexts.map((context) => (
                              <option
                                key={context.curriculum_course_id}
                                value={context.curriculum_course_id}
                              >
                                {context.programs
                                  .map(
                                    (program) =>
                                      `${program.study_program_code} ${program.study_program_name}`,
                                  )
                                  .join(", ")}{" "}
                                {context.course_code} {context.course_name}
                                {context.can_edit ? "" : " (hanya lihat)"}
                              </option>
                            ))}
                          </select>
                        </label>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {missingContextCount > 0 && (
                <p
                  role="alert"
                  className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy"
                >
                  Pilih konteks kurikulum untuk {missingContextCount} kelas
                  sebelum menyimpan assignment.
                </p>
              )}
              {saveError && (
                <p
                  role="alert"
                  className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy"
                >
                  {saveError}
                </p>
              )}
              <div className="space-y-4">
                {preview.data.map((group) => (
                  <section
                    key={group.curriculum_course_id}
                    aria-labelledby={`assignment-course-${group.curriculum_course_id}`}
                    className="rounded-xl border border-border bg-surface"
                  >
                    <div className="border-b border-border p-4">
                      <h3
                        id={`assignment-course-${group.curriculum_course_id}`}
                        className="font-heading text-base font-bold text-navy"
                      >
                        {group.course_code} {group.course_name}
                      </h3>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <p className="text-xs text-muted">
                          {group.programs
                            .map(
                              (program) =>
                                `${program.study_program_code} ${program.study_program_name}`,
                            )
                            .join(", ") ||
                            group.study_program_code ||
                            "Program studi tidak tersedia"}
                        </p>
                        <span className="rounded border border-border bg-background px-2 py-1 text-xs font-semibold text-navy">
                          {group.can_edit ? "Dapat diubah" : "Hanya lihat"}
                        </span>
                      </div>
                      <div className="mt-3">
                        <h4 className="text-xs font-semibold text-foreground">
                          Urutan Tim Pengajar gabungan
                        </h4>
                        {group.pool.length > 0 ? (
                          <ol className="mt-2 flex flex-wrap gap-2 text-xs text-navy">
                            {group.pool.map((lecturer) => (
                              <li
                                key={lecturer.user_id}
                                className="rounded-md border border-border bg-background px-2 py-1"
                              >
                                {lecturer.position}. {lecturer.lecturer_name}
                                {lecturer.is_pjmk ? " (PJ MK)" : ""}
                              </li>
                            ))}
                          </ol>
                        ) : (
                          <p className="mt-2 text-sm text-muted">
                            Tim Pengajar belum tersedia.
                          </p>
                        )}
                      </div>
                    </div>
                    <ul className="divide-y divide-border">
                      {group.classes.map((item, index) => {
                        const contextSelected =
                          selectedContexts[item.class_section_id] ===
                          group.curriculum_course_id
                        const editable =
                          group.can_edit && item.can_edit && contextSelected
                        const decision = contextSelected
                          ? decisions[item.class_section_id]
                          : undefined
                        const options = group.pool.map((lecturer) => ({
                          value: lecturer.user_id,
                          label: `${lecturer.position}. ${lecturer.lecturer_name}`,
                          hint: lecturer.is_pjmk ? "PJ MK" : undefined,
                        }))
                        if (
                          decision &&
                          !options.some(
                            (option) => option.value === decision.user_id,
                          )
                        ) {
                          options.push({
                            value: decision.user_id,
                            label: lecturerName(group, item, decision.user_id),
                            hint: "Tersimpan",
                          })
                        }
                        const controlId = `assignment-${item.class_section_id}-${group.curriculum_course_id}`
                        return (
                          <li
                            key={`${item.class_section_id}-${group.curriculum_course_id}`}
                            className="space-y-3 p-4"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <p className="font-semibold text-navy">
                                  Kelas {item.section_code}
                                  <span className="ml-2 text-xs font-normal text-muted">
                                    Urutan snake {index + 1}
                                  </span>
                                </p>
                                <p className="mt-1 text-xs text-muted">
                                  Calon preview:{" "}
                                  {item.candidate?.lecturer_name ??
                                    "Tidak tersedia"}
                                </p>
                                {item.existing_assignment && (
                                  <p className="mt-1 text-xs text-muted">
                                    Assignment tersimpan:{" "}
                                    {item.existing_assignment.lecturer_name}
                                  </p>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {decision && (
                                  <span className="rounded border border-border bg-background px-2 py-1 text-xs text-navy">
                                    {decision.source === "manual"
                                      ? "Manual"
                                      : "Otomatis"}
                                  </span>
                                )}
                                {decision?.is_pinned && (
                                  <span className="rounded border border-gold bg-gold/15 px-2 py-1 text-xs font-semibold text-navy">
                                    Dipin
                                  </span>
                                )}
                              </div>
                            </div>
                            {decision && editable ? (
                              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                                <SearchableCombobox
                                  id={controlId}
                                  label="Dosen pengajar"
                                  options={options}
                                  value={decision.user_id}
                                  onChange={(userId) =>
                                    updateDecision(group, item, {
                                      user_id: userId,
                                    })
                                  }
                                  placeholder="Pilih dosen dari Tim Pengajar"
                                  searchPlaceholder="Cari nama dosen"
                                  emptyLabel="Tidak ada dosen yang cocok."
                                  disabled={saving || deleting}
                                  className={comboboxClass}
                                  describeBy={`${controlId}-help`}
                                />
                                <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm font-medium text-navy">
                                  <input
                                    type="checkbox"
                                    checked={decision.is_pinned}
                                    disabled={saving || deleting}
                                    onChange={(event) =>
                                      updateDecision(group, item, {
                                        is_pinned: event.target.checked,
                                      })
                                    }
                                    className="h-5 w-5 rounded border-input text-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                  />
                                  <Pin className="h-4 w-4" aria-hidden="true" />{" "}
                                  Pin dosen
                                </label>
                              </div>
                            ) : (
                              <p className="text-sm text-muted">
                                {!contextSelected
                                  ? "Pilih konteks kurikulum kelas ini sebelum mengubah assignment."
                                  : !group.can_edit || !item.can_edit
                                    ? "Assignment pada konteks ini hanya dapat dilihat."
                                    : "Belum ada calon dosen untuk kelas ini."}
                              </p>
                            )}
                            {decision && editable && (
                              <p
                                id={`${controlId}-help`}
                                className="text-xs text-muted"
                              >
                                Mengubah dosen menjadikannya assignment manual.
                                Pin mempertahankan pilihan pada preview
                                berikutnya.
                              </p>
                            )}
                            {item.existing_assignment && editable && (
                              <button
                                type="button"
                                onClick={() => {
                                  setDeleteError(null)
                                  setDeleteTarget({ group, item })
                                }}
                                disabled={saving || deleting}
                                className={cn(
                                  buttonClass,
                                  "border border-orange/40 text-orange hover:bg-orange/10",
                                )}
                              >
                                <Trash2
                                  className="h-4 w-4"
                                  aria-hidden="true"
                                />{" "}
                                Hapus assignment
                              </button>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </section>
                ))}
              </div>
              <div className="sticky bottom-0 flex flex-col gap-3 border-t border-border bg-surface/95 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-muted">
                  {missingContextCount > 0
                    ? "Pilih konteks kurikulum terlebih dahulu."
                    : dirty
                      ? "Perubahan belum disimpan."
                      : "Tidak ada perubahan baru."}
                </p>
                <button
                  type="button"
                  onClick={() => void save()}
                  disabled={
                    !dirty || saving || deleting || missingContextCount > 0
                  }
                  className={cn(
                    buttonClass,
                    "bg-navy text-white hover:bg-navy-light",
                  )}
                  aria-busy={saving}
                >
                  <Save className="h-4 w-4" aria-hidden="true" />
                  {saving ? "Menyimpan..." : "Simpan assignment"}
                </button>
              </div>
            </>
          )}
        </>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Hapus assignment pengajar?"
          body={
            <p className="text-sm text-muted">
              Assignment {deleteTarget.group.course_code} kelas{" "}
              {deleteTarget.item.section_code} akan dihapus. Preview berikutnya
              dapat menghitung calon baru.
            </p>
          }
          confirmLabel="Hapus assignment"
          tone="orange"
          busy={deleting}
          errorMessage={deleteError}
          onCancel={() => {
            if (!deleting) setDeleteTarget(null)
          }}
          onConfirm={removeAssignment}
        />
      )}
    </section>
  )
}
