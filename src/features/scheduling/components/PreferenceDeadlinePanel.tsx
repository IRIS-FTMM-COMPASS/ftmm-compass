import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react"
import { RefreshCw, Save } from "lucide-react"
import { apiErrorMessage } from "@/shared/api/client"
import { useSession } from "@/features/auth/session"
import { cn } from "@/shared/utils"
import {
  schedulingService,
  type BoardProgramStatus,
  type PreferencePeriod,
  type PreferenceSummaryItem,
  type PreferenceSummaryResponse,
  type SchedulePeriodSettings,
} from "../schedulingService"

const inputClass =
  "min-h-11 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
const buttonClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"

function toDateTimeLocal(value: string | null): string {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function formatDeadline(value: string | null): string {
  if (!value) return "Belum ditetapkan"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Belum ditetapkan"
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(date)
}

function SummaryRows({ items }: { items: PreferenceSummaryItem[] }) {
  return (
    <>
      <div
        role="region"
        aria-label="Tabel kelengkapan preferensi dosen"
        tabIndex={0}
        className="hidden overflow-x-auto md:block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <table className="w-full table-fixed min-w-[800px] border-collapse text-left text-sm">
          <caption className="sr-only">Kelengkapan preferensi dosen</caption>
          <colgroup>
            <col className="w-[24%]" />
            <col className="w-[12%]" />
            <col className="w-[16%]" />
            <col className="w-[13%]" />
            <col className="w-[15%]" />
            <col className="w-[20%]" />
          </colgroup>
          <thead>
            <tr className="border-b border-border text-xs font-semibold text-muted">
              <th scope="col" className="px-3 py-3">
                Nama dosen
              </th>
              <th scope="col" className="px-3 py-3">
                Prodi
              </th>
              <th scope="col" className="px-3 py-3">
                Status
              </th>
              <th scope="col" className="px-3 py-3 text-right">
                Jam preferensi
              </th>
              <th scope="col" className="px-3 py-3 text-right">
                Blok tidak tersedia
              </th>
              <th scope="col" className="px-3 py-3">
                Deadline
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((item) => {
              const deadline = formatDeadline(item.deadline)
              return (
                <tr key={item.user_id}>
                  <th scope="row" className="px-3 py-3 font-medium text-navy">
                    <div className="truncate" title={item.full_name}>
                      {item.full_name}
                    </div>
                  </th>
                  <td className="px-3 py-3 text-muted">
                    <div className="truncate" title={item.study_program_code}>
                      {item.study_program_code}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={cn(
                        "rounded border px-2 py-1 text-xs font-semibold",
                        item.status === "filled"
                          ? "border-teal/40 bg-teal/15 text-navy"
                          : "border-gold/40 bg-gold/15 text-navy",
                      )}
                    >
                      {item.status === "filled"
                        ? "Sudah mengisi"
                        : "Belum mengisi"}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    {item.preferred_count}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    {item.unavailable_count}
                  </td>
                  <td className="px-3 py-3 text-muted">
                    <div className="truncate" title={deadline}>
                      {deadline}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-border md:hidden">
        {items.map((item) => (
          <li key={item.user_id} className="space-y-2 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="font-semibold text-navy">{item.full_name}</p>
              <span
                className={cn(
                  "rounded border px-2 py-1 text-xs font-semibold",
                  item.status === "filled"
                    ? "border-teal/40 bg-teal/15 text-navy"
                    : "border-gold/40 bg-gold/15 text-navy",
                )}
              >
                {item.status === "filled" ? "Sudah mengisi" : "Belum mengisi"}
              </span>
            </div>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted">Prodi</dt>
                <dd className="mt-0.5 text-foreground">
                  {item.study_program_code}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Deadline</dt>
                <dd className="mt-0.5 text-foreground">
                  {formatDeadline(item.deadline)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Jam preferensi</dt>
                <dd className="mt-0.5 tabular-nums text-foreground">
                  {item.preferred_count}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Blok tidak tersedia</dt>
                <dd className="mt-0.5 tabular-nums text-foreground">
                  {item.unavailable_count}
                </dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>
    </>
  )
}

export default function PreferenceDeadlinePanel() {
  const { user } = useSession()
  const isAdmin = user?.role === "admin"
  const canManage =
    isAdmin ||
    (user?.role === "lecturer" && user.is_program_coordinator === true)
  const [periods, setPeriods] = useState<PreferencePeriod[]>([])
  const [periodId, setPeriodId] = useState("")
  const [scopeId, setScopeId] = useState("")
  const [programs, setPrograms] = useState<BoardProgramStatus[]>([])
  const [periodsLoading, setPeriodsLoading] = useState(true)
  const [periodsError, setPeriodsError] = useState<string | null>(null)
  const [programsLoading, setProgramsLoading] = useState(false)
  const [programsError, setProgramsError] = useState<string | null>(null)
  const [periodReloadKey, setPeriodReloadKey] = useState(0)
  const [programReloadKey, setProgramReloadKey] = useState(0)
  const [settings, setSettings] = useState<SchedulePeriodSettings | null>(null)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [settingsReloadKey, setSettingsReloadKey] = useState(0)
  const [deadlineDraft, setDeadlineDraft] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [summary, setSummary] = useState<PreferenceSummaryResponse | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const settingsSequence = useRef(0)
  const summarySequence = useRef(0)

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
        setPeriodId(
          (current) =>
            current ||
            response.meta.current_academic_period_id ||
            response.data[0]?.academic_period_id ||
            "",
        )
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
  }, [canManage, periodReloadKey])

  useEffect(() => {
    if (!canManage || !isAdmin) return
    let active = true
    setProgramsLoading(true)
    setProgramsError(null)
    schedulingService
      .getBoard()
      .then((response) => {
        if (active) setPrograms(response.data.programs)
      })
      .catch((cause) => {
        if (active)
          setProgramsError(
            apiErrorMessage(cause, "Daftar program studi tidak dapat dimuat."),
          )
      })
      .finally(() => {
        if (active) setProgramsLoading(false)
      })
    return () => {
      active = false
    }
  }, [canManage, isAdmin, programReloadKey])

  useEffect(() => {
    if (!canManage || !periodId) return
    const sequence = ++settingsSequence.current
    setSettingsLoading(true)
    setSettingsError(null)
    setSaveError(null)
    setNotice(null)
    schedulingService
      .getPeriodSettings({
        academic_period_id: periodId,
        ...(scopeId ? { study_program_id: scopeId } : {}),
      })
      .then((response) => {
        if (sequence !== settingsSequence.current) return
        setSettings(response)
        setDeadlineDraft(toDateTimeLocal(response.preference_deadline))
      })
      .catch((cause) => {
        if (sequence !== settingsSequence.current) return
        setSettings(null)
        setDeadlineDraft("")
        setSettingsError(
          apiErrorMessage(cause, "Pengaturan deadline tidak dapat dimuat."),
        )
      })
      .finally(() => {
        if (sequence === settingsSequence.current) setSettingsLoading(false)
      })
    return () => {
      settingsSequence.current += 1
    }
  }, [canManage, periodId, scopeId, settingsReloadKey])

  const loadSummary = useCallback(async () => {
    if (!canManage || !periodId) return
    const sequence = ++summarySequence.current
    setSummaryLoading(true)
    setSummaryError(null)
    try {
      const response = await schedulingService.getPreferenceSummary({
        academic_period_id: periodId,
        ...(scopeId ? { study_program_id: scopeId } : {}),
      })
      if (sequence === summarySequence.current) setSummary(response)
    } catch (cause) {
      if (sequence === summarySequence.current) {
        setSummary(null)
        setSummaryError(
          apiErrorMessage(cause, "Ringkasan kelengkapan tidak dapat dimuat."),
        )
      }
    } finally {
      if (sequence === summarySequence.current) setSummaryLoading(false)
    }
  }, [canManage, periodId, scopeId])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  const deadlineDirty =
    settings !== null &&
    deadlineDraft !== toDateTimeLocal(settings.preference_deadline)
  const locked = Boolean(settings?.finalized_at)
  const scopeLabel = settings
    ? settings.study_program_id
      ? `${settings.study_program_code ?? "Prodi"}${
          settings.study_program_name ? `, ${settings.study_program_name}` : ""
        }`
      : "Global, seluruh program studi"
    : isAdmin
      ? scopeId
        ? (programs.find((program) => program.study_program_id === scopeId)
            ?.study_program_code ?? "Program studi")
        : "Global, seluruh program studi"
      : "Program studi Anda"
  const counts = useMemo(
    () => ({
      total: summary?.meta.total ?? 0,
      filled: summary?.meta.filled ?? 0,
      empty: summary?.meta.empty ?? 0,
    }),
    [summary],
  )

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!settings || !deadlineDirty || saving || locked) return
    const date = deadlineDraft ? new Date(deadlineDraft) : null
    if (date && Number.isNaN(date.getTime())) {
      setSaveError("Masukkan tanggal dan jam deadline yang valid.")
      return
    }
    setSaving(true)
    setSaveError(null)
    try {
      const response = await schedulingService.updatePeriodSettings({
        academic_period_id: periodId,
        study_program_id: settings.study_program_id,
        preference_deadline: date?.toISOString() ?? null,
      })
      setSettings(response)
      setDeadlineDraft(toDateTimeLocal(response.preference_deadline))
      setNotice(
        response.preference_deadline
          ? "Deadline preferensi tersimpan."
          : "Deadline preferensi dihapus.",
      )
      await loadSummary()
    } catch (cause) {
      setSaveError(
        apiErrorMessage(cause, "Deadline preferensi gagal disimpan."),
      )
    } finally {
      setSaving(false)
    }
  }

  if (!canManage) return null

  return (
    <section
      aria-labelledby="preference-deadline-admin-title"
      className="space-y-4"
    >
      <div className="space-y-1">
        <h2
          id="preference-deadline-admin-title"
          className="font-heading text-lg font-bold text-navy"
        >
          Deadline dan Kelengkapan Preferensi
        </h2>
        <p className="max-w-2xl text-sm text-muted">
          Tetapkan deadline untuk cakupan yang dipilih dan pantau kelengkapan
          dosen. Ringkasan ini hanya dapat dibaca, tidak dapat mengedit
          preferensi dosen.
        </p>
      </div>

      <div className="grid gap-3 rounded-xl border border-border bg-surface p-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
          Periode akademik
          <select
            value={periodId}
            disabled={periodsLoading || saving}
            onChange={(event) => {
              setPeriodId(event.target.value)
              setSummary(null)
            }}
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
        {isAdmin ? (
          <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
            Cakupan deadline
            <select
              value={scopeId}
              disabled={programsLoading || saving}
              onChange={(event) => {
                setScopeId(event.target.value)
                setSummary(null)
              }}
              className={inputClass}
            >
              <option value="">Global, seluruh program studi</option>
              {programs.map((program) => (
                <option
                  key={program.study_program_id}
                  value={program.study_program_id}
                >
                  {program.study_program_code}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="flex flex-col gap-1 text-xs font-semibold text-navy">
            Cakupan deadline
            <p className="flex min-h-11 items-center rounded-lg border border-border bg-background px-3 text-sm font-normal text-foreground">
              Program studi sesuai sesi PJ Prodi
            </p>
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
      {isAdmin && programsError && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-orange/30 bg-orange/10 p-4"
        >
          <span className="text-sm text-navy">{programsError}</span>
          <button
            type="button"
            onClick={() => setProgramReloadKey((key) => key + 1)}
            className={cn(
              buttonClass,
              "border border-orange bg-surface text-orange",
            )}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> Coba lagi
          </button>
        </div>
      )}

      {!periodsLoading && !periodsError && periodId && (
        <>
          {notice && (
            <p
              role="status"
              className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-3 text-sm text-navy"
            >
              {notice}
            </p>
          )}
          <section
            aria-labelledby="deadline-setting-title"
            className="space-y-4 rounded-xl border border-border bg-surface p-4"
          >
            <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3
                  id="deadline-setting-title"
                  className="font-heading text-base font-bold text-navy"
                >
                  Pengaturan deadline
                </h3>
                <p className="mt-1 text-sm text-muted">Cakupan: {scopeLabel}</p>
              </div>
              {settings && (
                <p className="text-xs text-muted">
                  Revision input: {settings.input_revision}
                </p>
              )}
            </div>
            {settingsLoading ? (
              <p role="status" className="text-sm text-muted">
                Memuat pengaturan deadline...
              </p>
            ) : settingsError ? (
              <div role="alert" className="flex flex-wrap items-center gap-3">
                <span className="text-sm text-orange">{settingsError}</span>
                <button
                  type="button"
                  onClick={() => setSettingsReloadKey((key) => key + 1)}
                  className={cn(
                    buttonClass,
                    "border border-border bg-surface text-navy",
                  )}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" /> Muat
                  ulang
                </button>
              </div>
            ) : settings ? (
              <form onSubmit={save} className="space-y-4">
                {locked && (
                  <p
                    role="status"
                    className="rounded-lg border border-gold bg-gold/15 px-4 py-3 text-sm text-navy"
                  >
                    Cakupan ini sudah final. Deadline hanya dapat diubah setelah
                    jadwal dibuka kembali.
                  </p>
                )}
                <div className="grid gap-3 lg:grid-cols-[minmax(0,20rem)_auto] lg:items-end">
                  <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
                    Deadline preferensi
                    <input
                      type="datetime-local"
                      value={deadlineDraft}
                      disabled={saving || locked}
                      onChange={(event) => {
                        setDeadlineDraft(event.target.value)
                        setSaveError(null)
                      }}
                      aria-describedby="deadline-help"
                      className={inputClass}
                    />
                  </label>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <button
                      type="submit"
                      disabled={!deadlineDirty || saving || locked}
                      className={cn(
                        buttonClass,
                        "bg-navy text-white hover:bg-navy-light",
                      )}
                      aria-busy={saving}
                    >
                      <Save className="h-4 w-4" aria-hidden="true" />{" "}
                      {saving ? "Menyimpan..." : "Simpan deadline"}
                    </button>
                    <button
                      type="button"
                      disabled={
                        !settings.preference_deadline || saving || locked
                      }
                      onClick={() => {
                        setDeadlineDraft("")
                        setSaveError(null)
                      }}
                      className={cn(
                        buttonClass,
                        "border border-orange/40 text-orange hover:bg-orange/10",
                      )}
                    >
                      Kosongkan deadline
                    </button>
                  </div>
                </div>
                <p id="deadline-help" className="text-xs text-muted">
                  Kosongkan tanggal untuk menghapus deadline, lalu simpan.
                  Deadline tidak mengunci edit dosen sebelum jadwal final.
                </p>
                {saveError && (
                  <p
                    role="alert"
                    className="rounded-lg border border-orange/30 bg-orange/10 p-3 text-sm text-navy"
                  >
                    {saveError}
                  </p>
                )}
              </form>
            ) : null}
          </section>

          <section
            aria-labelledby="preference-completeness-title"
            className="space-y-3"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3
                  id="preference-completeness-title"
                  className="font-heading text-base font-bold text-navy"
                >
                  Kelengkapan preferensi
                </h3>
                <p className="mt-1 text-sm text-muted">
                  {summaryLoading
                    ? "Memuat ringkasan..."
                    : `${counts.total} dosen, ${counts.filled} sudah mengisi, ${counts.empty} belum mengisi`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void loadSummary()}
                disabled={summaryLoading}
                className={cn(
                  buttonClass,
                  "border border-border bg-surface text-navy hover:bg-accent",
                )}
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" /> Muat ulang
                ringkasan
              </button>
            </div>
            {summaryLoading ? (
              <p
                role="status"
                className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-muted"
              >
                Memuat kelengkapan dosen...
              </p>
            ) : summaryError ? (
              <div
                role="alert"
                className="flex flex-wrap items-center gap-3 rounded-xl border border-orange/30 bg-orange/10 p-4"
              >
                <span className="text-sm text-navy">{summaryError}</span>
                <button
                  type="button"
                  onClick={() => void loadSummary()}
                  className={cn(
                    buttonClass,
                    "border border-orange bg-surface text-orange",
                  )}
                >
                  Coba lagi
                </button>
              </div>
            ) : summary && summary.data.length === 0 ? (
              <p className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-muted">
                Belum ada dosen aktif dalam cakupan ini.
              </p>
            ) : summary ? (
              <div className="rounded-xl border border-border bg-surface">
                <SummaryRows items={summary.data} />
              </div>
            ) : null}
          </section>
        </>
      )}
    </section>
  )
}
