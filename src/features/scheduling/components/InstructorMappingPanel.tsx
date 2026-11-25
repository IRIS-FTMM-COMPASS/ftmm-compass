import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react"
import {
  ArrowDown,
  ArrowUp,
  Copy,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react"
import { useSession } from "@/features/auth/session"
import {
  apiErrorMessage,
  apiFieldErrors,
  ApiError,
  type ApiFieldIssue,
} from "@/shared/api/client"
import SearchableCombobox, {
  type ComboboxOption,
} from "@/shared/ui/SearchableCombobox"
import ConfirmDialog from "@/shared/ui/ConfirmDialog"
import FormFieldError from "@/shared/ui/FormFieldError"
import { cn } from "@/shared/utils"
import {
  schedulingService,
  type CurriculumCourseOption,
  type InstructorCandidateItem,
  type InstructorPeriod,
  type InstructorReferenceCreateRequest,
  type InstructorReferenceResponse,
  type InstructorReferenceRole,
} from "../schedulingService"

const inputClass =
  "min-h-11 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
const buttonClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"

interface ReferenceForm {
  curriculum_course_id: string
  instructor_name: string
  user_id: string
  instructor_role: InstructorReferenceRole
  external: boolean
}

const EMPTY_FORM: ReferenceForm = {
  curriculum_course_id: "",
  instructor_name: "",
  user_id: "",
  instructor_role: "pjmk",
  external: false,
}

type FormFieldName = "curriculum_course_id" | "instructor_name" | "user_id" | "instructor_role"

type FormFieldErrors = Record<FormFieldName | "formSummary", string | null>

const FORM_FIELD_NAMES: FormFieldName[] = [
  "curriculum_course_id",
  "instructor_name",
  "user_id",
  "instructor_role",
]

const EMPTY_FIELD_ERRORS: FormFieldErrors = {
  curriculum_course_id: null,
  instructor_name: null,
  user_id: null,
  instructor_role: null,
  formSummary: null,
}

const PJMK_ACCOUNT_MESSAGE = "Pilih akun dosen aktif untuk PJ MK."
const PJMK_EXISTS_MESSAGE =
  "Mata kuliah ini sudah memiliki PJ MK. Ubah PJ MK yang ada."
const TEAM_MEMBER_MESSAGE =
  "Pengajar ini sudah terdaftar dalam Tim Pengajar mata kuliah tersebut."

function teamMemberErrorField(form: ReferenceForm): FormFieldName {
  return form.user_id && !form.external ? "user_id" : "instructor_name"
}

function apiIssueMessage(
  field: FormFieldName | undefined,
  code: string | undefined,
): string {
  if (code === "invalid_position") return "Posisi pengajar tidak valid."
  if (code === "required" || code === "missing") {
    if (field === "curriculum_course_id")
      return "Pilih mata kuliah terlebih dahulu."
    if (field === "instructor_name") return "Nama pengajar wajib diisi."
    if (field === "user_id") return "Pilih akun dosen."
    if (field === "instructor_role") return "Pilih jenis referensi."
    return "Lengkapi data yang wajib diisi."
  }
  if (code === "invalid_name") return "Nama pengajar tidak boleh kosong."
  if (code === "literal_error") {
    if (field === "curriculum_course_id") return "Mata kuliah tidak valid."
    if (field === "instructor_name") return "Nama pengajar tidak valid."
    if (field === "user_id") return "Akun dosen tidak valid."
    if (field === "instructor_role") return "Jenis referensi tidak valid."
    return "Periksa kembali data yang diisi."
  }
  if (field === "curriculum_course_id") return "Pilih mata kuliah yang valid."
  if (field === "instructor_name") return "Periksa nama pengajar."
  if (field === "user_id") return "Periksa akun dosen yang dipilih."
  if (field === "instructor_role") return "Pilih jenis referensi yang valid."
  return "Periksa kembali data yang diisi."
}

function mapApiFieldIssue(issue: ApiFieldIssue, form: ReferenceForm): {
  field: FormFieldName | "formSummary"
  message: string
} | null {
  const field = FORM_FIELD_NAMES.find((name) => issue.field.endsWith(name))
  const code = issue.code
  if (code === "pjmk_requires_account")
    return { field: "user_id", message: PJMK_ACCOUNT_MESSAGE }
  if (code === "pjmk_exists")
    return { field: "curriculum_course_id", message: PJMK_EXISTS_MESSAGE }
  if (code === "team_member_exists")
    return { field: teamMemberErrorField(form), message: TEAM_MEMBER_MESSAGE }
  if (code === "invalid_position")
    return { field: "formSummary", message: apiIssueMessage(field, code) }
  if (code === "invalid_name")
    return { field: "instructor_name", message: apiIssueMessage(field, code) }
  if (field) return { field, message: apiIssueMessage(field, code) }
  return null
}

function formErrorsFromApi(
  cause: unknown,
  form: ReferenceForm,
): FormFieldErrors {
  const errors: FormFieldErrors = { ...EMPTY_FIELD_ERRORS }
  const topCode = cause instanceof ApiError ? cause.code : undefined
  if (topCode === "pjmk_requires_account") errors.user_id = PJMK_ACCOUNT_MESSAGE
  if (topCode === "pjmk_exists")
    errors.curriculum_course_id = PJMK_EXISTS_MESSAGE
  if (topCode === "team_member_exists")
    errors[teamMemberErrorField(form)] = TEAM_MEMBER_MESSAGE
  const issues = apiFieldErrors(cause)
  for (const issue of issues) {
    const mapped = mapApiFieldIssue(issue, form)
    if (!mapped) continue
    if (mapped.field === "formSummary") {
      errors.formSummary = mapped.message
    } else if (!errors[mapped.field]) {
      errors[mapped.field] = mapped.message
    }
  }
  if (!FORM_FIELD_NAMES.some((field) => errors[field]) && !errors.formSummary) {
    errors.formSummary =
      issues.length > 0 || topCode === "validation_error"
        ? "Periksa kembali data yang diisi."
        : apiErrorMessage(cause, "Referensi pengajar gagal disimpan.")
  }
  return errors
}

function periodLabel(period: InstructorPeriod): string {
  const term =
    period.term === "ganjil"
      ? "Ganjil"
      : period.term === "genap"
        ? "Genap"
        : `Semester ${period.semester_number}`
  return `${period.academic_year_start}/${period.academic_year_start + 1} ${term}`
}

function eligibilityLabel(reference: InstructorReferenceResponse): string {
  if (reference.instructor_role === "pjmk") return "PJ MK berakun"
  if (reference.eligibility_reason === "external")
    return "Dosen eksternal, belum dapat auto-assign"
  if (reference.eligibility_reason === "inactive_account")
    return "Akun nonaktif, belum dapat auto-assign"
  if (reference.eligibility_reason === "not_lecturer")
    return "Bukan akun dosen, belum dapat auto-assign"
  return reference.can_auto_assign === false
    ? "Belum dapat auto-assign"
    : "Dapat auto-assign"
}

function referencePool(
  references: InstructorReferenceResponse[],
): InstructorReferenceResponse[] {
  return [...references].sort((a, b) => {
    if (a.instructor_role === "pjmk" && b.instructor_role !== "pjmk") return -1
    if (b.instructor_role === "pjmk" && a.instructor_role !== "pjmk") return 1
    return (a.position ?? 0) - (b.position ?? 0)
  })
}

export interface InstructorMappingPanelProps {
  initialAcademicPeriodId?: string | null
  initialCurriculumCourseId?: string | null
  initialReferenceId?: string | null
  initialRole?: InstructorReferenceRole
  bootstrapKey?: number
  onContinueToAssignment?: (payload: {
    academicPeriodId: string
    curriculumCourseId: string
  }) => void
}

export default function InstructorMappingPanel({
  initialAcademicPeriodId = null,
  initialCurriculumCourseId = null,
  initialReferenceId = null,
  initialRole = "pjmk",
  bootstrapKey = 0,
  onContinueToAssignment,
}: InstructorMappingPanelProps) {
  const { user } = useSession()
  const canManage =
    user?.role === "admin" ||
    (user?.role === "lecturer" && user.is_program_coordinator === true)
  const consumedBootstrapKey = useRef(0)
  const formRef = useRef<HTMLFormElement>(null)
  const panelRef = useRef<HTMLElement>(null)
  const formOpenerRef = useRef<HTMLElement | null>(null)
  const [periods, setPeriods] = useState<InstructorPeriod[]>([])
  const [periodId, setPeriodId] = useState("")
  const [periodsLoading, setPeriodsLoading] = useState(true)
  const [periodsError, setPeriodsError] = useState<string | null>(null)
  const [periodReloadKey, setPeriodReloadKey] = useState(0)
  const [references, setReferences] = useState<InstructorReferenceResponse[]>(
    [],
  )
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [candidates, setCandidates] = useState<InstructorCandidateItem[]>([])
  const [candidatesLoading, setCandidatesLoading] = useState(false)
  const [candidateError, setCandidateError] = useState<string | null>(null)
  const [candidateReloadKey, setCandidateReloadKey] = useState(0)
  const [courses, setCourses] = useState<CurriculumCourseOption[]>([])
  const [coursesLoading, setCoursesLoading] = useState(false)
  const [coursesError, setCoursesError] = useState<string | null>(null)
  const [courseReloadKey, setCourseReloadKey] = useState(0)
  const [courseFilter, setCourseFilter] = useState("all")
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<ReferenceForm>(EMPTY_FORM)
  const [fieldErrors, setFieldErrors] =
    useState<FormFieldErrors>(EMPTY_FIELD_ERRORS)
  const [savingForm, setSavingForm] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [lastSavedCourseId, setLastSavedCourseId] = useState<string | null>(
    null,
  )
  const [deleteTarget, setDeleteTarget] =
    useState<InstructorReferenceResponse | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [copyOpen, setCopyOpen] = useState(false)
  const [copying, setCopying] = useState(false)
  const [copyError, setCopyError] = useState<string | null>(null)

  useEffect(() => {
    if (!canManage) return
    let active = true
    setPeriodsLoading(true)
    setPeriodsError(null)
    schedulingService
      .listInstructorPeriods()
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
            response.data.find((period) => period.is_active)
              ?.academic_period_id ||
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

  useEffect(() => {
    if (!canManage || !periodId) return
    let active = true
    setLoading(true)
    setLoadError(null)
    setNotice(null)
    setFormOpen(false)
    setEditingId(null)
    schedulingService
      .listInstructorReferences({ academic_period_id: periodId })
      .then((items) => {
        if (active)
          setReferences(
            items.filter(
              (item) =>
                item.instructor_role === "pjmk" ||
                item.instructor_role === "teaching_team",
            ),
          )
      })
      .catch((cause) => {
        if (active) {
          setReferences([])
          setLoadError(
            apiErrorMessage(cause, "Pemetaan pengajar tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [canManage, periodId, reloadKey])

  useEffect(() => {
    if (!canManage || !periodId) return
    let active = true
    setCandidatesLoading(true)
    setCandidateError(null)
    schedulingService
      .listInstructorCandidates({
        academic_period_id: periodId,
        page: 1,
        page_size: 100,
      })
      .then((items) => {
        if (active) setCandidates(items)
      })
      .catch((cause) => {
        if (active) {
          setCandidates([])
          setCandidateError(
            apiErrorMessage(cause, "Daftar akun dosen tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setCandidatesLoading(false)
      })
    return () => {
      active = false
    }
  }, [canManage, periodId, candidateReloadKey])

  useEffect(() => {
    if (!canManage) return
    let active = true
    setCoursesLoading(true)
    setCoursesError(null)
    schedulingService
      .listCurriculumCourses()
      .then((items) => {
        if (active) setCourses(items)
      })
      .catch((cause) => {
        if (active)
          setCoursesError(
            apiErrorMessage(cause, "Daftar mata kuliah tidak dapat dimuat."),
          )
      })
      .finally(() => {
        if (active) setCoursesLoading(false)
      })
    return () => {
      active = false
    }
  }, [canManage, courseReloadKey])

  const activeCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.is_active),
    [candidates],
  )
  const candidateOptions = useMemo<ComboboxOption[]>(() => {
    const options = activeCandidates.map((candidate) => ({
      value: candidate.user_id,
      label: candidate.full_name,
      hint: candidate.study_program_code ?? "FTMM",
    }))
    const current = candidates.find(
      (candidate) => candidate.user_id === form.user_id,
    )
    if (
      current &&
      !options.some((option) => option.value === current.user_id)
    ) {
      options.unshift({
        value: current.user_id,
        label: `${current.full_name} (akun nonaktif)`,
        hint: current.study_program_code ?? "FTMM",
      })
    }
    return options
  }, [activeCandidates, candidates, form.user_id])

  const programNames = useMemo(() => {
    const names = new Map<string, string>()
    for (const item of references) {
      if (item.study_program_id && item.study_program_name)
        names.set(item.study_program_id, item.study_program_name)
    }
    return names
  }, [references])
  const courseOptions = useMemo<ComboboxOption[]>(
    () =>
      courses.map((course) => ({
        value: course.curriculum_course_id,
        label: `${course.course_code} ${course.course_name}`,
        hint: programNames.get(course.study_program_id),
      })),
    [courses, programNames],
  )

  const groups = useMemo(() => {
    const byCourse = new Map<string, InstructorReferenceResponse[]>()
    for (const reference of references) {
      if (!reference.curriculum_course_id) continue
      const group = byCourse.get(reference.curriculum_course_id) ?? []
      group.push(reference)
      byCourse.set(reference.curriculum_course_id, group)
    }
    return [...byCourse.entries()]
      .map(([courseId, items]) => {
        const course = courses.find(
          (item) => item.curriculum_course_id === courseId,
        )
        return { courseId, course, references: referencePool(items) }
      })
      .filter(
        (group) => courseFilter === "all" || group.courseId === courseFilter,
      )
      .sort((a, b) =>
        (a.course?.course_code ?? "").localeCompare(
          b.course?.course_code ?? "",
        ),
      )
  }, [references, courses, courseFilter])

  const selectedCourse = courses.find(
    (course) => course.curriculum_course_id === form.curriculum_course_id,
  )
  const selectedCourseReferences = references.filter(
    (reference) => reference.curriculum_course_id === form.curriculum_course_id,
  )
  const selectedCourseHasPjmk = selectedCourseReferences.some(
    (reference) =>
      reference.instructor_role === "pjmk" &&
      reference.reference_id !== editingId,
  )
  const previousPeriod = useMemo(() => {
    const index = periods.findIndex(
      (period) => period.academic_period_id === periodId,
    )
    return index > 0 ? periods[index - 1] : null
  }, [periods, periodId])

  const openCreate = (
    role: InstructorReferenceRole = "pjmk",
    courseId = "",
  ) => {
    const opener = document.activeElement
    formOpenerRef.current =
      opener instanceof HTMLElement && panelRef.current?.contains(opener)
        ? opener
        : null
    setEditingId(null)
    setForm({
      ...EMPTY_FORM,
      instructor_role: role,
      curriculum_course_id: courseId,
    })
    setFieldErrors(EMPTY_FIELD_ERRORS)
    setActionError(null)
    setFormOpen(true)
  }

  const openEdit = (reference: InstructorReferenceResponse) => {
    const opener = document.activeElement
    formOpenerRef.current =
      opener instanceof HTMLElement && panelRef.current?.contains(opener)
        ? opener
        : null
    setEditingId(reference.reference_id)
    setForm({
      curriculum_course_id: reference.curriculum_course_id ?? "",
      instructor_name: reference.instructor_name,
      user_id: reference.user_id ?? "",
      instructor_role: reference.instructor_role as InstructorReferenceRole,
      external: !reference.user_id,
    })
    setFieldErrors(EMPTY_FIELD_ERRORS)
    setActionError(null)
    setFormOpen(true)
  }

  const restoreFormOpener = useCallback(() => {
    const opener = formOpenerRef.current
    formOpenerRef.current = null
    window.requestAnimationFrame(() => opener?.focus())
  }, [])

  const focusFirstInvalid = useCallback(() => {
    window.requestAnimationFrame(() => {
      const invalid = formRef.current?.querySelector<HTMLElement>(
        '[aria-invalid="true"]',
      )
      if (!invalid) return
      invalid.focus({ preventScroll: true })
      invalid.scrollIntoView({ block: "center" })
    })
  }, [])

  const updateForm = (update: (current: ReferenceForm) => ReferenceForm) => {
    setForm(update)
    setFieldErrors(EMPTY_FIELD_ERRORS)
  }

  const closeForm = useCallback(() => {
    if (savingForm) return
    setFormOpen(false)
    setEditingId(null)
    restoreFormOpener()
  }, [restoreFormOpener, savingForm])

  useEffect(() => {
    if (
      !canManage ||
      bootstrapKey === 0 ||
      consumedBootstrapKey.current === bootstrapKey ||
      loading ||
      loadError ||
      !periodId ||
      (initialAcademicPeriodId !== null && periodId !== initialAcademicPeriodId)
    ) {
      return
    }
    if (initialReferenceId) {
      const reference = references.find(
        (item) => item.reference_id === initialReferenceId,
      )
      if (!reference) {
        consumedBootstrapKey.current = bootstrapKey
        setActionError(
          "PJ MK terkait tidak ditemukan pada cakupan atau periode ini.",
        )
        return
      }
      consumedBootstrapKey.current = bootstrapKey
      openEdit(reference)
      return
    }
    if (initialCurriculumCourseId) {
      consumedBootstrapKey.current = bootstrapKey
      openCreate(initialRole, initialCurriculumCourseId)
    }
  }, [
    bootstrapKey,
    canManage,
    initialAcademicPeriodId,
    initialReferenceId,
    initialRole,
    loadError,
    loading,
    periodId,
    references,
  ])

  useEffect(() => {
    if (!formOpen) return
    formRef.current?.focus({ preventScroll: true })
    formRef.current?.scrollIntoView({ block: "start" })
  }, [formOpen])
  useEffect(() => {
    if (!formOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented || savingForm) return
      event.preventDefault()
      closeForm()
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [closeForm, formOpen, savingForm])

  const submitForm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextErrors: FormFieldErrors = { ...EMPTY_FIELD_ERRORS }
    if (!form.curriculum_course_id) {
      nextErrors.curriculum_course_id = "Pilih mata kuliah terlebih dahulu."
    }
    if (!form.instructor_name.trim() && (form.external || !form.user_id)) {
      nextErrors[form.external ? "instructor_name" : "user_id"] =
        "Pilih akun dosen atau tulis nama dosen eksternal."
    }
    if (form.instructor_role === "pjmk" && (!form.user_id || form.external)) {
      nextErrors.user_id = "PJ MK wajib memilih akun dosen aktif."
    } else if (
      form.instructor_role === "pjmk" &&
      !activeCandidates.some((candidate) => candidate.user_id === form.user_id)
    ) {
      nextErrors.user_id = PJMK_ACCOUNT_MESSAGE
    }
    if (
      !editingId &&
      form.instructor_role === "pjmk" &&
      selectedCourseHasPjmk
    ) {
      nextErrors.curriculum_course_id = PJMK_EXISTS_MESSAGE
    }
    if (FORM_FIELD_NAMES.some((field) => nextErrors[field])) {
      setFieldErrors(nextErrors)
      focusFirstInvalid()
      return
    }
    const selectedCandidate = candidates.find(
      (candidate) => candidate.user_id === form.user_id,
    )
    const instructorName =
      form.user_id && !form.external
        ? (selectedCandidate?.full_name ?? form.instructor_name.trim())
        : form.instructor_name.trim()
    setSavingForm(true)
    setFieldErrors(EMPTY_FIELD_ERRORS)
    try {
      if (editingId) {
        const updated = await schedulingService.updateInstructorReference(
          editingId,
          {
            instructor_name: instructorName,
            user_id: form.external ? null : form.user_id || null,
            academic_period_id: periodId,
          },
        )
        setReferences((current) =>
          current.map((item) =>
            item.reference_id === updated.reference_id ? updated : item,
          ),
        )
        setNotice("Referensi pengajar diperbarui.")
      } else {
        const payload: InstructorReferenceCreateRequest = {
          curriculum_course_id: form.curriculum_course_id,
          instructor_name: instructorName,
          instructor_role: form.instructor_role,
          user_id: form.external ? null : form.user_id || null,
          academic_period_id: periodId,
          position:
            form.instructor_role === "pjmk"
              ? 1
              : selectedCourseReferences.length + 1,
        }
        const created =
          await schedulingService.createInstructorReference(payload)
        setReferences((current) => [...current, created])
        setNotice(
          form.instructor_role === "pjmk"
            ? "PJ MK ditambahkan ke posisi pertama Tim Pengajar."
            : "Anggota Tim Pengajar ditambahkan.",
        )
      }
      setLastSavedCourseId(form.curriculum_course_id)
      setFormOpen(false)
      setEditingId(null)
      restoreFormOpener()
    } catch (cause) {
      setFieldErrors(formErrorsFromApi(cause, form))
      focusFirstInvalid()
    } finally {
      setSavingForm(false)
    }
  }

  const saveOrder = async (courseId: string, orderedIds: string[]) => {
    setBusyId(courseId)
    setActionError(null)
    setNotice(null)
    try {
      const response = await schedulingService.orderInstructorReferences({
        curriculum_course_id: courseId,
        academic_period_id: periodId,
        ordered_reference_ids: orderedIds,
      })
      setReferences((current) => [
        ...current.filter((item) => item.curriculum_course_id !== courseId),
        ...response.data,
      ])
      setNotice("Urutan Tim Pengajar disimpan.")
      setLastSavedCourseId(courseId)
    } catch (cause) {
      setActionError(
        apiErrorMessage(cause, "Urutan Tim Pengajar gagal disimpan."),
      )
    } finally {
      setBusyId(null)
    }
  }

  const moveReference = (
    courseId: string,
    index: number,
    direction: -1 | 1,
  ) => {
    const group = groups.find((item) => item.courseId === courseId)
    if (!group) return
    const ids = group.references.map((item) => item.reference_id)
    const target = index + direction
    if (target < 0 || target >= ids.length) return
    if (group.references[index].instructor_role === "pjmk" && direction === -1)
      return
    if (group.references[target].instructor_role === "pjmk" && direction === 1)
      return
    const firstId = ids[index]
    ids[index] = ids[target]
    ids[target] = firstId
    setReferences((current) =>
      current.map((reference) => {
        const position = ids.indexOf(reference.reference_id)
        return position >= 0
          ? { ...reference, position: position + 1 }
          : reference
      }),
    )
    void saveOrder(courseId, ids)
  }

  const deleteReference = async () => {
    if (!deleteTarget) return
    setBusyId(deleteTarget.reference_id)
    setDeleteError(null)
    try {
      await schedulingService.deleteInstructorReference(
        deleteTarget.reference_id,
        periodId,
      )
      setReferences((current) =>
        current.filter(
          (item) => item.reference_id !== deleteTarget.reference_id,
        ),
      )
      setDeleteTarget(null)
      setNotice("Referensi pengajar dihapus.")
    } catch (cause) {
      setDeleteError(
        apiErrorMessage(cause, "Referensi pengajar gagal dihapus."),
      )
    } finally {
      setBusyId(null)
    }
  }

  const copyForward = async () => {
    if (!previousPeriod) return
    setCopying(true)
    setCopyError(null)
    try {
      const response = await schedulingService.copyInstructorReferences({
        from_academic_period_id: previousPeriod.academic_period_id,
        academic_period_id: periodId,
      })
      setReferences((current) => {
        const copiedIds = new Set(
          response.data.map((item) => item.reference_id),
        )
        return [
          ...current.filter((item) => !copiedIds.has(item.reference_id)),
          ...response.data,
        ]
      })
      setNotice(
        `${response.meta.copied} referensi disalin, ${response.meta.skipped} dilewati.`,
      )
      setCopyOpen(false)
    } catch (cause) {
      setCopyError(
        apiErrorMessage(cause, "Pemetaan periode sebelumnya gagal disalin."),
      )
    } finally {
      setCopying(false)
    }
  }

  if (!canManage) {
    return (
      <section className="rounded-xl border border-border bg-surface p-6">
        <h2 className="font-heading text-lg font-bold text-navy">
          PJ MK dan Tim Pengajar
        </h2>
        <p className="mt-2 text-sm text-muted">
          Pengelolaan pemetaan hanya tersedia untuk PJ Prodi dan admin.
        </p>
      </section>
    )
  }

  return (
    <section
      ref={panelRef}
      aria-labelledby="mapping-title"
      className="flex flex-col gap-4"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2
            id="mapping-title"
            className="font-heading text-xl font-bold text-navy"
          >
            PJ MK dan Tim Pengajar
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Atur satu PJ MK berakun dan urutan pool pengajar untuk setiap mata
            kuliah pada periode ini.
          </p>
        </div>
        <div className="w-full xl:max-w-sm">
          {periodsLoading ? (
            <p role="status" className="mt-2 text-sm text-muted">
              Memuat periode...
            </p>
          ) : periodsError ? (
            <div
              role="alert"
              className="mt-2 flex flex-wrap items-center gap-2"
            >
              <span className="text-sm text-orange">{periodsError}</span>
              <button
                type="button"
                onClick={() => setPeriodReloadKey((key) => key + 1)}
                className={cn(buttonClass, "border border-border text-navy")}
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" /> Coba lagi
              </button>
            </div>
          ) : periods.length === 0 ? (
            <p className="mt-2 text-sm text-muted">
              Belum ada periode akademik.
            </p>
          ) : (
            <SearchableCombobox
              id="mapping-period"
              label="Periode akademik"
              options={periods.map((period) => ({
                value: period.academic_period_id,
                label: periodLabel(period),
                hint: period.is_active ? "Aktif" : undefined,
              }))}
              value={periodId}
              onChange={setPeriodId}
              placeholder="Pilih periode"
              searchPlaceholder="Cari tahun atau semester"
              emptyLabel="Periode tidak ditemukan."
              className="mt-2"
            />
          )}
        </div>
        <button
          type="button"
          disabled={courseFilter === "all" || !onContinueToAssignment}
          title={
            courseFilter === "all"
              ? "Pilih mata kuliah terlebih dahulu"
              : "Buka Penugasan Kelas untuk mata kuliah ini"
          }
          onClick={() =>
            onContinueToAssignment?.({
              academicPeriodId: periodId,
              curriculumCourseId: courseFilter,
            })
          }
          className={cn(
            buttonClass,
            "mt-3 border border-navy bg-navy text-white hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          Lanjut ke Penugasan Kelas
        </button>
      </div>

      {periodId && (
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <button
            type="button"
            onClick={() => openCreate()}
            disabled={coursesLoading || courses.length === 0}
            className={cn(
              buttonClass,
              "border border-navy bg-navy text-white hover:bg-navy-light",
            )}
          >
            <Plus className="h-4 w-4" aria-hidden="true" /> Tambah PJ MK
          </button>
          <button
            type="button"
            onClick={() => {
              setCopyError(null)
              setCopyOpen(true)
            }}
            disabled={!previousPeriod}
            className={cn(
              buttonClass,
              "border border-border bg-surface text-navy hover:bg-accent",
            )}
          >
            <Copy className="h-4 w-4" aria-hidden="true" /> Salin periode
            sebelumnya
          </button>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className={cn(
              buttonClass,
              "border border-border bg-surface text-navy hover:bg-accent",
            )}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> Muat ulang
          </button>
        </div>
      )}

      {notice && (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-accent px-4 py-3 text-sm text-navy"
        >
          <span>{notice}</span>
          {lastSavedCourseId && onContinueToAssignment && (
            <button
              type="button"
              onClick={() =>
                onContinueToAssignment({
                  academicPeriodId: periodId,
                  curriculumCourseId: lastSavedCourseId,
                })
              }
              className={cn(
                buttonClass,
                "border border-navy bg-navy text-white hover:bg-navy-light",
              )}
            >
              Lanjut atur penugasan kelas
            </button>
          )}
        </div>
      )}
      {actionError && (
        <p
          role="alert"
          className="rounded-lg border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy"
        >
          {actionError}
        </p>
      )}

      {formOpen && (
        <form
          ref={formRef}
          onSubmit={submitForm}
          noValidate
          tabIndex={-1}
          aria-labelledby="mapping-form-title"
          className="scroll-mt-4 rounded-xl border border-border bg-surface p-4 sm:p-6"
        >
          <div className="flex items-start justify-between gap-4">
            <h3
              id="mapping-form-title"
              className="font-heading text-lg font-bold text-navy"
            >
              {editingId
                ? "Ubah referensi pengajar"
                : "Tambah referensi pengajar"}
            </h3>
            <button
              type="button"
              aria-label="Tutup formulir"
              onClick={closeForm}
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-border text-navy hover:bg-accent"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          {fieldErrors.formSummary && (
            <p
              id="mapping-form-summary"
              role="alert"
              className="mt-4 rounded-lg border border-orange/30 bg-orange/10 p-3 text-sm text-navy"
            >
              {fieldErrors.formSummary}
            </p>
          )}
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2 text-sm font-semibold">
              <label htmlFor="mapping-role">Jenis referensi</label>
              <select
                id="mapping-role"
                value={form.instructor_role}
                disabled={Boolean(editingId)}
                onChange={(event) =>
                  updateForm((current) => ({
                    ...current,
                    instructor_role: event.target
                      .value as InstructorReferenceRole,
                    external: false,
                    user_id: "",
                  }))
                }
                aria-invalid={Boolean(fieldErrors.instructor_role)}
                aria-describedby={
                  fieldErrors.instructor_role ? "mapping-role-error" : undefined
                }
                className={inputClass}
              >
                <option value="pjmk">PJ MK</option>
                <option value="teaching_team">Tim Pengajar</option>
              </select>
              <FormFieldError
                id="mapping-role-error"
                message={fieldErrors.instructor_role}
              />
            </div>
            <div className="flex flex-col gap-2">
              <label
                htmlFor="mapping-course-trigger"
                className="text-sm font-semibold"
              >
                Mata kuliah
              </label>
              {coursesLoading ? (
                <p role="status" className="text-sm text-muted">
                  Memuat mata kuliah...
                </p>
              ) : coursesError ? (
                <div role="alert" className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-orange">{coursesError}</span>
                  <button
                    type="button"
                    onClick={() => setCourseReloadKey((key) => key + 1)}
                    className={cn(
                      buttonClass,
                      "border border-orange text-orange",
                    )}
                  >
                    Coba lagi
                  </button>
                </div>
              ) : (
                <SearchableCombobox
                  id="mapping-course"
                  options={courseOptions}
                  value={form.curriculum_course_id}
                  onChange={(value) =>
                    updateForm((current) => ({
                      ...current,
                      curriculum_course_id: value,
                    }))
                  }
                  placeholder="Pilih mata kuliah"
                  searchPlaceholder="Cari kode atau nama mata kuliah"
                  disabled={Boolean(editingId) || savingForm}
                  invalid={Boolean(fieldErrors.curriculum_course_id)}
                  errorId="mapping-course-error"
                />
              )}
              <FormFieldError
                id="mapping-course-error"
                message={fieldErrors.curriculum_course_id}
              />
              {selectedCourse &&
                programNames.get(selectedCourse.study_program_id) && (
                  <p className="text-xs text-muted">
                    Prodi: {programNames.get(selectedCourse.study_program_id)}
                  </p>
                )}
            </div>
            {form.instructor_role === "teaching_team" && (
              <label className="flex min-h-11 items-center gap-3 text-sm font-semibold md:col-span-2">
                <input
                  type="checkbox"
                  checked={form.external}
                  onChange={(event) =>
                    updateForm((current) => ({
                      ...current,
                      external: event.target.checked,
                      user_id: event.target.checked ? "" : current.user_id,
                      instructor_name: event.target.checked
                        ? current.instructor_name
                        : "",
                    }))
                  }
                  className="h-5 w-5 accent-navy"
                />{" "}
                Dosen eksternal tanpa akun
              </label>
            )}
            {!form.external && (
              <div className="flex flex-col gap-2 md:col-span-2">
                {candidatesLoading ? (
                  <p role="status" className="text-sm text-muted">
                    Memuat akun dosen...
                  </p>
                ) : candidateError ? (
                  <div
                    role="alert"
                    className="flex flex-wrap items-center gap-2"
                  >
                    <span className="text-sm text-orange">
                      {candidateError}
                    </span>
                    <button
                      type="button"
                      onClick={() => setCandidateReloadKey((key) => key + 1)}
                      className={cn(
                        buttonClass,
                        "border border-orange text-orange",
                      )}
                    >
                      Coba lagi
                    </button>
                  </div>
                ) : (
                  <SearchableCombobox
                    id="mapping-lecturer"
                    label={`Akun dosen${
                      form.instructor_role === "pjmk" ? " (wajib)" : ""
                    }`}
                    options={candidateOptions}
                    value={form.user_id}
                    onChange={(value) => {
                      const candidate = activeCandidates.find(
                        (item) => item.user_id === value,
                      )
                      updateForm((current) => ({
                        ...current,
                        user_id: value,
                        instructor_name:
                          candidate?.full_name ?? current.instructor_name,
                      }))
                    }}
                    placeholder="Pilih akun dosen"
                    searchPlaceholder="Cari nama dosen"
                    emptyLabel="Akun dosen tidak ditemukan."
                    disabled={savingForm}
                    invalid={Boolean(fieldErrors.user_id)}
                    errorId="mapping-lecturer-error"
                  />
                )}
                <FormFieldError
                  id="mapping-lecturer-error"
                  message={fieldErrors.user_id}
                />
              </div>
            )}
            {form.external && (
              <div className="flex flex-col gap-2 text-sm font-semibold md:col-span-2">
                <label htmlFor="mapping-instructor-name">
                  Nama dosen eksternal
                </label>
                <input
                  id="mapping-instructor-name"
                  value={form.instructor_name}
                  onChange={(event) =>
                    updateForm((current) => ({
                      ...current,
                      instructor_name: event.target.value,
                    }))
                  }
                  aria-invalid={Boolean(fieldErrors.instructor_name)}
                  aria-describedby={
                    fieldErrors.instructor_name
                      ? "mapping-instructor-name-error"
                      : undefined
                  }
                  className={inputClass}
                  placeholder="Nama lengkap"
                />
                <FormFieldError
                  id="mapping-instructor-name-error"
                  message={fieldErrors.instructor_name}
                />
                <span className="text-xs font-normal text-muted">
                  Dosen eksternal dapat dicatat, tetapi belum dapat mendapat
                  auto-assignment sampai memiliki akun dosen.
                </span>
              </div>
            )}
          </div>
          <div className="mt-6 flex flex-col-reverse gap-3 border-t border-border pt-4 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={closeForm}
              disabled={savingForm}
              className={cn(buttonClass, "border border-border text-navy")}
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={savingForm || coursesLoading || candidatesLoading}
              className={cn(
                buttonClass,
                "border border-navy bg-navy text-white hover:bg-navy-light",
              )}
              aria-busy={savingForm}
            >
              {savingForm
                ? "Menyimpan..."
                : editingId
                  ? "Simpan perubahan"
                  : "Tambah referensi"}
            </button>
          </div>
        </form>
      )}

      {loading && (
        <p
          role="status"
          className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-muted"
        >
          Memuat pemetaan pengajar...
        </p>
      )}
      {!loading && loadError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-orange/30 bg-orange/10 p-4"
        >
          <span className="text-sm text-navy">{loadError}</span>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className={cn(buttonClass, "border border-orange text-orange")}
          >
            Coba lagi
          </button>
        </div>
      )}
      {!loading && !loadError && (
        <>
          <div className="max-w-xl">
            <label
              htmlFor="mapping-course-filter-trigger"
              className="mb-2 block text-sm font-semibold"
            >
              Filter mata kuliah
            </label>
            <SearchableCombobox
              id="mapping-course-filter"
              options={[
                { value: "all", label: "Semua mata kuliah" },
                ...courseOptions,
              ]}
              value={courseFilter}
              onChange={setCourseFilter}
              placeholder="Semua mata kuliah"
              searchPlaceholder="Cari mata kuliah"
            />
          </div>
          {groups.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface p-8 text-center">
              <h3 className="font-heading text-lg font-bold text-navy">
                Belum ada pemetaan pada periode ini
              </h3>
              <p className="mx-auto mt-2 max-w-lg text-sm text-muted">
                Tambahkan PJ MK berakun, lalu susun Tim Pengajar. Anda juga
                dapat menyalin pemetaan periode sebelumnya.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {groups.map((group) => {
                const pjmk = group.references.find(
                  (item) => item.instructor_role === "pjmk",
                )
                return (
                  <article
                    key={group.courseId}
                    className="rounded-xl border border-border bg-surface p-4 sm:p-6"
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <h3 className="font-heading text-lg font-bold text-navy">
                          {group.course?.course_code ?? "Mata kuliah"}{" "}
                          {group.course?.course_name ?? ""}
                        </h3>
                        <p className="mt-1 text-sm text-muted">
                          {pjmk
                            ? `PJ MK: ${pjmk.lecturer_name ?? pjmk.instructor_name}`
                            : "PJ MK belum ditentukan. Mata kuliah belum siap dijadwalkan."}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {!pjmk && (
                          <button
                            type="button"
                            onClick={() => openCreate("pjmk", group.courseId)}
                            className={cn(
                              buttonClass,
                              "border border-navy text-navy",
                            )}
                          >
                            <Plus className="h-4 w-4" aria-hidden="true" />{" "}
                            Tambah PJ MK
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() =>
                            openCreate("teaching_team", group.courseId)
                          }
                          className={cn(
                            buttonClass,
                            "border border-border text-navy",
                          )}
                        >
                          <Plus className="h-4 w-4" aria-hidden="true" /> Tambah
                          anggota
                        </button>
                      </div>
                    </div>
                    <h4 className="mt-6 text-sm font-bold">
                      Urutan Tim Pengajar
                    </h4>
                    <ol className="mt-3 flex flex-col gap-2">
                      {group.references.map((reference, index) => (
                        <li
                          key={reference.reference_id}
                          className="flex flex-col gap-3 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-navy">
                              {index + 1}.{" "}
                              {reference.instructor_role === "pjmk"
                                ? "PJ MK"
                                : "Tim Pengajar"}
                              :{" "}
                              {reference.lecturer_name ??
                                reference.instructor_name}
                            </p>
                            <p className="mt-1 text-xs text-muted">
                              {eligibilityLabel(reference)}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              aria-label={`Naikkan ${reference.instructor_name}`}
                              disabled={
                                busyId === group.courseId ||
                                index === 0 ||
                                reference.instructor_role === "pjmk"
                              }
                              onClick={() =>
                                moveReference(group.courseId, index, -1)
                              }
                              className={cn(
                                buttonClass,
                                "min-w-11 border border-border text-navy",
                              )}
                            >
                              <ArrowUp className="h-4 w-4" aria-hidden="true" />
                            </button>
                            <button
                              type="button"
                              aria-label={`Turunkan ${reference.instructor_name}`}
                              disabled={
                                busyId === group.courseId ||
                                index === group.references.length - 1 ||
                                reference.instructor_role === "pjmk"
                              }
                              onClick={() =>
                                moveReference(group.courseId, index, 1)
                              }
                              className={cn(
                                buttonClass,
                                "min-w-11 border border-border text-navy",
                              )}
                            >
                              <ArrowDown
                                className="h-4 w-4"
                                aria-hidden="true"
                              />
                            </button>
                            <button
                              type="button"
                              onClick={() => openEdit(reference)}
                              className={cn(
                                buttonClass,
                                "border border-border text-navy",
                              )}
                            >
                              <Pencil className="h-4 w-4" aria-hidden="true" />{" "}
                              Ubah
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setDeleteError(null)
                                setDeleteTarget(reference)
                              }}
                              className={cn(
                                buttonClass,
                                "border border-orange/40 text-orange",
                              )}
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />{" "}
                              Hapus
                            </button>
                          </div>
                        </li>
                      ))}
                    </ol>
                    <p className="mt-3 text-xs text-muted">
                      PJ MK tetap pada posisi pertama. Urutan dipakai untuk
                      auto-assignment kelas paralel dan bukan jadwal mengajar
                      tetap.
                    </p>
                  </article>
                )
              })}
            </div>
          )}
        </>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Hapus referensi pengajar?"
          body={
            <p className="text-sm text-muted">
              {deleteTarget.instructor_name} akan dihapus dari mata kuliah pada
              periode ini.
            </p>
          }
          confirmLabel="Hapus referensi"
          tone="orange"
          busy={busyId === deleteTarget.reference_id}
          errorMessage={deleteError}
          onCancel={() => {
            if (busyId !== deleteTarget.reference_id) setDeleteTarget(null)
          }}
          onConfirm={deleteReference}
        />
      )}
      {copyOpen && previousPeriod && (
        <ConfirmDialog
          title="Salin pemetaan periode sebelumnya?"
          body={
            <p className="text-sm text-muted">
              Referensi dari {periodLabel(previousPeriod)} akan disalin ke
              periode ini. Referensi yang sudah ada tidak akan ditimpa.
            </p>
          }
          confirmLabel="Salin pemetaan"
          busy={copying}
          errorMessage={copyError}
          onCancel={() => {
            if (!copying) setCopyOpen(false)
          }}
          onConfirm={copyForward}
        />
      )}
    </section>
  )
}
