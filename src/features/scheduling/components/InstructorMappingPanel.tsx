import { useEffect, useMemo, useState, type FormEvent } from "react"
import { AlertCircle, Plus, RefreshCw, Trash2 } from "lucide-react"
import { useSession } from "@/features/auth/session"
import {
  authService,
  authErrorMessage,
  type AdminAccount,
} from "@/features/auth/authService"
import {
  schedulingService,
  type CurriculumCourseOption,
  type InstructorReferenceCreateRequest,
  type InstructorReferenceResponse,
  type InstructorReferenceRole,
} from "@/features/scheduling/schedulingService"
import { apiErrorMessage } from "@/shared/api/client"
import { cn } from "@/shared/utils"

const FILTERS = [
  { key: "all", label: "Semua" },
  { key: "unmapped", label: "Belum dipetakan" },
  { key: "mapped", label: "Sudah dipetakan" },
] as const

type FilterKey = typeof FILTERS[number]["key"]

const inputClass =
  "min-h-11 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
const buttonClass =
  "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer"

interface RoleOption {
  value: InstructorReferenceRole
  label: string
}

const ROLE_OPTIONS: RoleOption[] = [
  { value: "pjmk", label: "PJ MK" },
  { value: "teaching_team", label: "Tim Pengajar" },
  { value: "lecturer", label: "Dosen" },
  { value: "other", label: "Lainnya" },
]

interface ReferenceFormValues {
  curriculum_course_id: string
  instructor_name: string
  instructor_role: InstructorReferenceRole | ""
  user_id: string
}

type ReferenceFieldErrors = Partial<Record<"curriculum_course_id" | "instructor_name" | "instructor_role", string>>

const EMPTY_REFERENCE_FORM: ReferenceFormValues = {
  curriculum_course_id: "",
  instructor_name: "",
  instructor_role: "",
  user_id: "",
}

function roleLabel(role: string): string {
  return ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role
}

function RoleNotice() {
  return (
    <section
      aria-labelledby="mapping-title"
      className="rounded-xl border border-border bg-surface p-6 text-center"
    >
      <h2
        id="mapping-title"
        className="font-heading text-lg font-bold text-navy"
      >
        Pemetaan Pengajar
      </h2>
      <p className="mx-auto mt-2 max-w-lg text-sm text-muted">
        Pemetaan nama dosen pada mata kuliah ke akun tersedia bagi admin FTMM
        Compass dan PJ Prodi.
      </p>
    </section>
  )
}

export default function InstructorMappingPanel() {
  const { user } = useSession()
  const isAdmin = user?.role === "admin"
  const isPjProdi =
    user?.role === "lecturer" && user.is_program_coordinator === true
  const canManage = isAdmin || isPjProdi

  const [references, setReferences] = useState<InstructorReferenceResponse[]>(
    [],
  )
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const [lecturers, setLecturers] = useState<AdminAccount[]>([])
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true)
  const [accountError, setAccountError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [accountReloadKey, setAccountReloadKey] = useState(0)
  const [hasMoreLecturers, setHasMoreLecturers] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [filter, setFilter] = useState<FilterKey>("all")
  const [query, setQuery] = useState("")
  const [savingId, setSavingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [courses, setCourses] = useState<CurriculumCourseOption[]>([])
  const [isLoadingCourses, setIsLoadingCourses] = useState(true)
  const [courseError, setCourseError] = useState<string | null>(null)
  const [courseReloadKey, setCourseReloadKey] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const [referenceForm, setReferenceForm] =
    useState<ReferenceFormValues>(EMPTY_REFERENCE_FORM)
  const [referenceErrors, setReferenceErrors] = useState<ReferenceFieldErrors>(
    {},
  )
  const [isCreating, setIsCreating] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    if (!canManage) return
    let active = true
    setIsLoading(true)
    setLoadError(null)
    schedulingService
      .listInstructorReferences()
      .then((items) => {
        if (!active) return
        setReferences(items)
        setDrafts(
          Object.fromEntries(
            items.map((item): [string, string] => [
              item.reference_id,
              item.user_id ?? "",
            ]),
          ),
        )
      })
      .catch((cause) => {
        if (active) {
          setLoadError(
            apiErrorMessage(
              cause,
              "Daftar referensi pengajar tidak dapat dimuat.",
            ),
          )
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [canManage, reloadKey])

  useEffect(() => {
    if (!canManage) return
    let active = true
    setIsLoadingCourses(true)
    setCourseError(null)
    schedulingService
      .listCurriculumCourses()
      .then((items) => {
        if (active) setCourses(items)
      })
      .catch((cause) => {
        if (active) {
          setCourseError(
            apiErrorMessage(cause, "Daftar mata kuliah tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setIsLoadingCourses(false)
      })
    return () => {
      active = false
    }
  }, [canManage, courseReloadKey])

  useEffect(() => {
    if (!canManage) return
    let active = true
    if (page === 1) setIsLoadingAccounts(true)
    else setIsLoadingMore(true)
    authService
      .listAccounts({ role: "lecturer", page, page_size: 100 })
      .then((result) => {
        if (!active) return
        setLecturers((previous) =>
          page === 1 ? result.items : [...previous, ...result.items],
        )
        setHasMoreLecturers(result.page * result.page_size < result.total)
        setAccountError(null)
      })
      .catch((cause) => {
        if (!active) return
        if (page === 1) setLecturers([])
        setAccountError(
          authErrorMessage(cause, "Daftar akun dosen tidak dapat dimuat."),
        )
      })
      .finally(() => {
        if (!active) return
        setIsLoadingAccounts(false)
        setIsLoadingMore(false)
      })
    return () => {
      active = false
    }
  }, [canManage, page, accountReloadKey])

  const lecturerOptions = useMemo(() => {
    const options: {
      id: string
      label: string
    }[] = []
    const seen = new Set<string>()
    for (const account of lecturers) {
      if (!account.is_active) continue
      const label = account.full_name?.trim()
        ? `${account.full_name} · ${account.email}`
        : account.email
      options.push({ id: account.user_id, label })
      seen.add(account.user_id)
    }
    for (const reference of references) {
      if (reference.user_id && !seen.has(reference.user_id)) {
        options.push({
          id: reference.user_id,
          label: reference.lecturer_name?.trim() || reference.user_id,
        })
        seen.add(reference.user_id)
      }
    }
    return options
  }, [lecturers, references])

  const counts = useMemo(
    () => ({
      all: references.length,
      unmapped: references.filter((item) => !item.is_mapped).length,
      mapped: references.filter((item) => item.is_mapped).length,
    }),
    [references],
  )

  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase("id-ID")
    return references.filter((item) => {
      if (filter === "unmapped" && item.is_mapped) return false
      if (filter === "mapped" && !item.is_mapped) return false
      if (!term) return true
      return [
        item.instructor_name,
        item.course_code,
        item.course_name,
        item.lecturer_name,
      ].some((value) => value?.toLocaleLowerCase("id-ID").includes(term))
    })
  }, [references, filter, query])

  const applyMapping = async (
    reference: InstructorReferenceResponse,
    userId: string | null,
  ) => {
    setSavingId(reference.reference_id)
    setActionError(null)
    setSuccess(null)
    try {
      const updated = await schedulingService.mapInstructor(
        reference.reference_id,
        userId,
      )
      setReferences((previous) =>
        previous.map((item) =>
          item.reference_id === updated.reference_id ? updated : item,
        ),
      )
      setDrafts((previous) => ({
        ...previous,
        [updated.reference_id]: updated.user_id ?? "",
      }))
      setSuccess(
        `${updated.instructor_name}: ${
          updated.is_mapped ? "pemetaan tersimpan" : "pemetaan dihapus"
        }.`,
      )
    } catch (cause) {
      setActionError(
        `${reference.instructor_name}: ${apiErrorMessage(
          cause,
          "Pemetaan gagal disimpan.",
        )}`,
      )
    } finally {
      setSavingId(null)
    }
  }

  const openReferenceForm = () => {
    setReferenceForm(EMPTY_REFERENCE_FORM)
    setReferenceErrors({})
    setActionError(null)
    setSuccess(null)
    setFormOpen(true)
  }

  const closeReferenceForm = () => {
    setFormOpen(false)
    setReferenceErrors({})
  }

  const createReference = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors: ReferenceFieldErrors = {}
    if (!referenceForm.curriculum_course_id) {
      errors.curriculum_course_id = "Mata kuliah wajib dipilih."
    }
    if (!referenceForm.instructor_name.trim()) {
      errors.instructor_name = "Nama pengajar wajib diisi."
    }
    if (!referenceForm.instructor_role) {
      errors.instructor_role = "Peran pengajar wajib dipilih."
    }
    setReferenceErrors(errors)
    if (Object.keys(errors).length > 0) return

    const payload: InstructorReferenceCreateRequest = {
      curriculum_course_id: referenceForm.curriculum_course_id,
      instructor_name: referenceForm.instructor_name.trim(),
      instructor_role: referenceForm.instructor_role as InstructorReferenceRole,
      user_id: referenceForm.user_id.trim() || null,
    }
    setIsCreating(true)
    setActionError(null)
    setSuccess(null)
    try {
      const created = await schedulingService.createInstructorReference(payload)
      setReferences((previous) => [created, ...previous])
      setDrafts((previous) => ({
        ...previous,
        [created.reference_id]: created.user_id ?? "",
      }))
      setFilter("all")
      setQuery("")
      setFormOpen(false)
      setReferenceForm(EMPTY_REFERENCE_FORM)
      setSuccess(`Referensi ${created.instructor_name} berhasil ditambahkan.`)
    } catch (cause) {
      setActionError(
        apiErrorMessage(cause, "Referensi pengajar gagal ditambahkan."),
      )
    } finally {
      setIsCreating(false)
    }
  }

  const removeReference = async (reference: InstructorReferenceResponse) => {
    setDeletingId(reference.reference_id)
    setActionError(null)
    setSuccess(null)
    try {
      await schedulingService.deleteInstructorReference(reference.reference_id)
      setReferences((previous) =>
        previous.filter((item) => item.reference_id !== reference.reference_id),
      )
      setDrafts((previous) => {
        const next = { ...previous }
        delete next[reference.reference_id]
        return next
      })
      setSuccess(`Referensi ${reference.instructor_name} dihapus.`)
    } catch (cause) {
      setActionError(
        `${reference.instructor_name}: ${apiErrorMessage(
          cause,
          "Referensi pengajar gagal dihapus.",
        )}`,
      )
    } finally {
      setDeletingId(null)
    }
  }

  if (!canManage) return <RoleNotice />

  return (
    <section aria-labelledby="mapping-title" className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2
            id="mapping-title"
            className="font-heading text-lg font-bold text-navy md:text-xl"
          >
            Pemetaan Pengajar
          </h2>
          <p className="text-xs text-muted">
            Hubungkan nama pengajar pada mata kuliah dengan akun agar jadwal
            dapat dicek terhadap ketersediaan dosen.
          </p>
        </div>
        <button
          type="button"
          onClick={formOpen ? closeReferenceForm : openReferenceForm}
          aria-expanded={formOpen}
          aria-controls="reference-form"
          className={cn(
            buttonClass,
            "border border-navy bg-navy text-white hover:bg-navy-light",
          )}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          {formOpen ? "Tutup formulir" : "Tambah referensi"}
        </button>
      </div>

      {success && (
        <p
          role="status"
          className="rounded-lg border border-border bg-accent px-4 py-2.5 text-xs text-navy"
        >
          {success}
        </p>
      )}

      {actionError && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-orange/30 bg-orange/10 px-3 py-2 text-xs text-navy"
        >
          <AlertCircle
            className="mt-0.5 h-4 w-4 shrink-0 text-orange"
            aria-hidden="true"
          />
          {actionError}
        </p>
      )}

      {formOpen && (
        <form
          noValidate
          id="reference-form"
          onSubmit={createReference}
          aria-labelledby="reference-form-title"
          className="space-y-4 rounded-xl border border-border bg-surface p-4"
        >
          <h3
            id="reference-form-title"
            className="font-heading text-base font-bold text-navy"
          >
            Tambah referensi pengajar
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <label
                htmlFor="reference-course"
                className="block text-xs font-semibold text-foreground"
              >
                Mata kuliah
              </label>
              {isLoadingCourses ? (
                <p
                  id="reference-course-status"
                  className="rounded-lg border border-border bg-background px-3 py-2.5 text-xs text-muted"
                >
                  Memuat mata kuliah...
                </p>
              ) : courseError ? (
                <div
                  role="alert"
                  className="flex flex-col gap-2 rounded-lg border border-orange/30 bg-orange/10 px-3 py-2 text-xs text-navy sm:flex-row sm:items-center sm:justify-between"
                >
                  <span>{courseError}</span>
                  <button
                    type="button"
                    onClick={() => setCourseReloadKey((key) => key + 1)}
                    className={cn(
                      buttonClass,
                      "border border-orange/40 bg-surface text-orange hover:bg-orange/10",
                    )}
                  >
                    <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                    Coba lagi
                  </button>
                </div>
              ) : courses.length === 0 ? (
                <p
                  id="reference-course-status"
                  className="rounded-lg border border-border bg-background px-3 py-2.5 text-xs text-muted"
                >
                  Belum ada mata kuliah pada kurikulum.
                </p>
              ) : (
                <select
                  id="reference-course"
                  value={referenceForm.curriculum_course_id}
                  onChange={(event) =>
                    setReferenceForm((previous) => ({
                      ...previous,
                      curriculum_course_id: event.target.value,
                    }))
                  }
                  aria-invalid={Boolean(referenceErrors.curriculum_course_id)}
                  aria-describedby={
                    referenceErrors.curriculum_course_id
                      ? "reference-course-error"
                      : undefined
                  }
                  className={inputClass}
                >
                  <option value="">Pilih mata kuliah</option>
                  {courses.map((course) => (
                    <option
                      key={course.curriculum_course_id}
                      value={course.curriculum_course_id}
                    >
                      {`${course.course_code || "Tanpa kode"} · ${
                        course.course_name || "Tanpa nama"
                      }`}
                    </option>
                  ))}
                </select>
              )}
              {referenceErrors.curriculum_course_id && (
                <p
                  id="reference-course-error"
                  role="alert"
                  className="text-xs text-orange"
                >
                  {referenceErrors.curriculum_course_id}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="reference-name"
                className="block text-xs font-semibold text-foreground"
              >
                Nama pengajar
              </label>
              <input
                id="reference-name"
                type="text"
                maxLength={100}
                value={referenceForm.instructor_name}
                onChange={(event) =>
                  setReferenceForm((previous) => ({
                    ...previous,
                    instructor_name: event.target.value,
                  }))
                }
                aria-invalid={Boolean(referenceErrors.instructor_name)}
                aria-describedby={
                  referenceErrors.instructor_name
                    ? "reference-name-error"
                    : undefined
                }
                placeholder="Nama sesuai mata kuliah"
                className={inputClass}
              />
              {referenceErrors.instructor_name && (
                <p
                  id="reference-name-error"
                  role="alert"
                  className="text-xs text-orange"
                >
                  {referenceErrors.instructor_name}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="reference-role"
                className="block text-xs font-semibold text-foreground"
              >
                Peran pengajar
              </label>
              <select
                id="reference-role"
                value={referenceForm.instructor_role}
                onChange={(event) =>
                  setReferenceForm((previous) => ({
                    ...previous,
                    instructor_role: event.target
                      .value as InstructorReferenceRole | "",
                  }))
                }
                aria-invalid={Boolean(referenceErrors.instructor_role)}
                aria-describedby={
                  referenceErrors.instructor_role
                    ? "reference-role-error"
                    : undefined
                }
                className={inputClass}
              >
                <option value="">Pilih peran</option>
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {referenceErrors.instructor_role && (
                <p
                  id="reference-role-error"
                  role="alert"
                  className="text-xs text-orange"
                >
                  {referenceErrors.instructor_role}
                </p>
              )}
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <label
                htmlFor="reference-account"
                className="block text-xs font-semibold text-foreground"
              >
                Akun dosen (opsional)
              </label>
              <select
                id="reference-account"
                value={referenceForm.user_id}
                onChange={(event) =>
                  setReferenceForm((previous) => ({
                    ...previous,
                    user_id: event.target.value,
                  }))
                }
                className={inputClass}
              >
                <option value="">Tanpa akun</option>
                {lecturerOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted">
                {isLoadingAccounts
                  ? "Memuat akun dosen..."
                  : "Akun dapat dipetakan kemudian dari daftar referensi."}
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="submit"
              disabled={isCreating}
              className={cn(
                buttonClass,
                "border border-navy bg-navy text-white hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              {isCreating ? "Menyimpan..." : "Simpan referensi"}
            </button>
            <button
              type="button"
              onClick={closeReferenceForm}
              disabled={isCreating}
              className={cn(
                buttonClass,
                "border border-border bg-surface text-navy hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              Batal
            </button>
          </div>
        </form>
      )}

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-3 sm:flex-row sm:items-end sm:justify-between">
        <div
          role="group"
          aria-label="Filter referensi pengajar"
          className="flex flex-wrap gap-2"
        >
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={filter === item.key}
              onClick={() => setFilter(item.key)}
              className={cn(
                buttonClass,
                filter === item.key
                  ? "border border-navy bg-navy text-white hover:bg-navy-light"
                  : "border border-border bg-surface text-navy hover:bg-secondary",
              )}
            >
              {item.label} ({counts[item.key]})
            </button>
          ))}
        </div>
        <div className="w-full space-y-1.5 sm:w-72">
          <label
            htmlFor="instructor-search"
            className="block text-xs font-semibold text-foreground"
          >
            Cari dosen atau mata kuliah
          </label>
          <input
            id="instructor-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Nama dosen atau kode MK"
            className={inputClass}
          />
        </div>
      </div>

      {accountError && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy sm:flex-row sm:items-center sm:justify-between"
        >
          <span>{accountError}</span>
          <button
            type="button"
            onClick={() => {
              setPage(1)
              setAccountReloadKey((key) => key + 1)
            }}
            className={cn(
              buttonClass,
              "border border-orange/40 bg-surface text-orange hover:bg-orange/10",
            )}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Coba lagi
          </button>
        </div>
      )}

      {isLoading && (
        <div className="rounded-xl border border-border bg-surface px-4 py-10 text-center">
          <p className="font-mono text-xs text-muted">
            Memuat referensi pengajar...
          </p>
        </div>
      )}

      {!isLoading && loadError && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy sm:flex-row sm:items-center sm:justify-between"
        >
          <span className="flex items-center gap-2">
            <AlertCircle
              className="h-4 w-4 shrink-0 text-orange"
              aria-hidden="true"
            />
            {loadError}
          </span>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className={cn(
              buttonClass,
              "border border-orange/40 bg-surface text-orange hover:bg-orange/10",
            )}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Coba lagi
          </button>
        </div>
      )}

      {!isLoading && !loadError && filtered.length === 0 && (
        <div className="rounded-xl border border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          {references.length === 0
            ? "Belum ada referensi pengajar. Gunakan tombol Tambah referensi untuk membuat referensi pertama."
            : "Tidak ada referensi yang cocok dengan pencarian atau filter ini."}
        </div>
      )}

      {!isLoading && !loadError && filtered.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full min-w-[54rem] text-left text-sm">
              <caption className="sr-only">
                Daftar referensi pengajar dan pemetaan akun dosen
              </caption>
              <thead className="bg-secondary text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Dosen
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Mata kuliah
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Akun saat ini
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Pilih akun
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Aksi
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((reference) => {
                  const selected = drafts[reference.reference_id] ?? ""
                  const changed = selected !== (reference.user_id ?? "")
                  const saving = savingId === reference.reference_id
                  return (
                    <tr
                      key={reference.reference_id}
                      className="text-foreground"
                    >
                      <th scope="row" className="px-4 py-3 font-semibold">
                        {reference.instructor_name}
                        <span className="mt-1 block text-xs font-normal text-muted">
                          {roleLabel(reference.instructor_role)}
                        </span>
                      </th>
                      <td className="px-4 py-3">
                        {reference.course_code ? (
                          <span className="font-mono text-xs text-navy">
                            {reference.course_code}
                          </span>
                        ) : null}
                        {reference.course_name ? (
                          <span className="block text-xs text-muted">
                            {reference.course_name}
                          </span>
                        ) : null}
                        {!reference.course_code && !reference.course_name
                          ? "—"
                          : null}
                      </td>
                      <td className="px-4 py-3">
                        {reference.is_mapped ? (
                          reference.lecturer_name?.trim() || "Akun dosen"
                        ) : (
                          <span className="text-xs text-muted">
                            Belum dipetakan
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {lecturerOptions.length > 0 ? (
                          <select
                            id={`mapping-${reference.reference_id}`}
                            aria-label={`Pilih akun dosen untuk ${reference.instructor_name}`}
                            value={selected}
                            disabled={saving}
                            onChange={(event) =>
                              setDrafts((previous) => ({
                                ...previous,
                                [reference.reference_id]: event.target.value,
                              }))
                            }
                            className={cn(inputClass, "min-w-48")}
                          >
                            <option value="">Belum dipetakan</option>
                            {lecturerOptions.map((option) => (
                              <option key={option.id} value={option.id}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className="text-xs text-muted">
                            {isLoadingAccounts
                              ? "Memuat akun dosen..."
                              : "Akun dosen tidak tersedia"}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          {changed && (
                            <button
                              type="button"
                              disabled={saving}
                              onClick={() =>
                                applyMapping(reference, selected || null)
                              }
                              className={cn(
                                buttonClass,
                                "border border-navy bg-navy text-white hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-60",
                              )}
                            >
                              {saving ? "Menyimpan..." : "Simpan"}
                            </button>
                          )}
                          {reference.is_mapped && !changed && (
                            <button
                              type="button"
                              disabled={saving}
                              onClick={() => applyMapping(reference, null)}
                              className={cn(
                                buttonClass,
                                "border border-border bg-surface text-orange hover:bg-orange/10 disabled:cursor-not-allowed disabled:opacity-60",
                              )}
                            >
                              {saving ? "Menyimpan..." : "Hapus pemetaan"}
                            </button>
                          )}
                          {!reference.is_mapped && !changed ? (
                            <span className="text-xs text-muted">—</span>
                          ) : null}
                          <button
                            type="button"
                            disabled={
                              saving || deletingId === reference.reference_id
                            }
                            onClick={() => removeReference(reference)}
                            aria-label={`Hapus referensi ${reference.instructor_name}`}
                            className={cn(
                              buttonClass,
                              "border border-border bg-surface text-orange hover:bg-orange/10 disabled:cursor-not-allowed disabled:opacity-60",
                            )}
                          >
                            <Trash2
                              className="h-3.5 w-3.5"
                              aria-hidden="true"
                            />
                            {deletingId === reference.reference_id
                              ? "Menghapus..."
                              : "Hapus"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {hasMoreLecturers && (
            <button
              type="button"
              disabled={isLoadingMore}
              onClick={() => setPage((current) => current + 1)}
              className={cn(
                buttonClass,
                "border border-border bg-surface text-navy hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              {isLoadingMore ? "Memuat..." : "Muat lebih banyak dosen"}
            </button>
          )}
        </>
      )}
    </section>
  )
}
