import { useEffect, useMemo, useState, type FormEvent } from "react"
import {
  AlertCircle,
  Copy,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react"
import { apiErrorMessage } from "@/shared/api/client"
import { useSession } from "@/features/auth/session"
import ConfirmDialog from "@/shared/ui/ConfirmDialog"
import { cn } from "@/shared/utils"
import SearchableCombobox from "@/shared/ui/SearchableCombobox"
import {
  schedulingService,
  type PreferencePeriod,
  type PreferenceResponse,
  type PreferenceSlot,
  type PreferenceWarning,
  type SchedulePeriodSettings,
} from "../schedulingService"

const DAYS = [
  { value: 1, label: "Senin" },
  { value: 2, label: "Selasa" },
  { value: 3, label: "Rabu" },
  { value: 4, label: "Kamis" },
  { value: 5, label: "Jumat" },
] as const

const START_TIMES = Array.from(
  { length: 10 },
  (_, index) => `${String(index + 7).padStart(2, "0")}:00`,
)
const END_TIMES = Array.from(
  { length: 10 },
  (_, index) => `${String(index + 8).padStart(2, "0")}:00`,
)
const inputClass =
  "min-h-11 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
const buttonClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"

function timeMinutes(value: string): number {
  const [hours, minutes] = value.split(":").map(Number)
  return hours * 60 + minutes
}

function validateSlots(slots: PreferenceSlot[]): string | null {
  for (let index = 0; index < slots.length; index += 1) {
    const slot = slots[index]
    const start = timeMinutes(slot.start_time)
    const end = timeMinutes(slot.end_time)
    if (
      !Number.isFinite(start) ||
      !Number.isFinite(end) ||
      start % 60 ||
      end % 60
    ) {
      return "Gunakan jam penuh, misalnya 07:00 atau 09:00."
    }
    if (
      start < 420 ||
      start >= 1020 ||
      end <= 420 ||
      end > 1020 ||
      end <= start
    ) {
      return "Setiap rentang harus berada di antara 07:00 dan 17:00, dengan jam selesai setelah jam mulai."
    }
    for (
      let otherIndex = index + 1;
      otherIndex < slots.length;
      otherIndex += 1
    ) {
      const other = slots[otherIndex]
      if (
        slot.day_of_week === other.day_of_week &&
        start < timeMinutes(other.end_time) &&
        timeMinutes(other.start_time) < end
      ) {
        return `Rentang ${DAYS[slot.day_of_week - 1].label} ${slot.start_time}-${slot.end_time} beririsan dengan rentang lain. Ubah atau hapus salah satu rentang.`
      }
    }
  }
  return null
}

function formatDeadline(value: string | null): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(date)
}

function warningMessage(warning: string | PreferenceWarning): string {
  if (typeof warning === "string") return warning
  if (warning.message) return warning.message
  const day =
    warning.day_name ??
    (warning.day_of_week ? DAYS[warning.day_of_week - 1]?.label : "")
  return [
    warning.course_code,
    warning.section_code,
    day,
    warning.overlap_start_time,
    warning.overlap_end_time,
  ]
    .filter(Boolean)
    .join(", ")
}

export default function PreferencePanel() {
  const { user } = useSession()
  const canReadSettings =
    user?.role === "admin" || user?.is_program_coordinator === true
  const [periods, setPeriods] = useState<PreferencePeriod[]>([])
  const [periodId, setPeriodId] = useState("")
  const [periodsLoading, setPeriodsLoading] = useState(true)
  const [periodsError, setPeriodsError] = useState<string | null>(null)
  const [periodReloadKey, setPeriodReloadKey] = useState(0)
  const [preference, setPreference] = useState<PreferenceResponse | null>(null)
  const [draft, setDraft] = useState<PreferenceSlot[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [editing, setEditing] = useState(false)
  const [periodSettings, setPeriodSettings] =
    useState<SchedulePeriodSettings | null>(null)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [settingsReloadKey, setSettingsReloadKey] = useState(0)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [copyTarget, setCopyTarget] = useState<PreferencePeriod | null>(null)
  const [copying, setCopying] = useState(false)
  const [copyError, setCopyError] = useState<string | null>(null)

  useEffect(() => {
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
  }, [periodReloadKey])

  useEffect(() => {
    if (!periodId || !canReadSettings) {
      setPeriodSettings(null)
      setSettingsError(null)
      setSettingsLoading(false)
      return
    }
    let active = true
    setSettingsError(null)
    setSettingsLoading(true)
    setPeriodSettings(null)
    schedulingService
      .getPeriodSettings({ academic_period_id: periodId })
      .then((response) => {
        if (active) setPeriodSettings(response)
      })
      .catch((cause) => {
        if (active)
          setSettingsError(
            apiErrorMessage(cause, "Deadline preferensi tidak dapat dimuat."),
          )
      })
      .finally(() => {
        if (active) setSettingsLoading(false)
      })
    return () => {
      active = false
    }
  }, [periodId, settingsReloadKey, canReadSettings])

  useEffect(() => {
    if (!periodId) return
    setLoading(true)
    let active = true
    setPreference(null)
    setLoadError(null)
    setNotice(null)
    setEditing(false)
    schedulingService
      .getMyPreferences(periodId)
      .then((response) => {
        if (active) setPreference(response)
      })
      .catch((cause) => {
        if (active) {
          setPreference(null)
          setLoadError(
            apiErrorMessage(cause, "Preferensi jadwal tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [periodId, reloadKey])

  const slots = useMemo(
    () =>
      (preference?.data ?? preference?.slots ?? []).map((slot) => ({
        ...slot,
        start_time: slot.start_time.slice(0, 5),
        end_time: slot.end_time.slice(0, 5),
      })),
    [preference],
  )
  const previousPeriod = useMemo(() => {
    const chronological = [...periods].sort(
      (a, b) =>
        b.academic_year_start - a.academic_year_start ||
        (b.semester_number ?? 0) - (a.semester_number ?? 0) ||
        (b.term ?? "").localeCompare(a.term ?? ""),
    )
    const index = chronological.findIndex(
      (period) => period.academic_period_id === periodId,
    )
    return index >= 0 ? (chronological[index + 1] ?? null) : null
  }, [periods, periodId])
  const locked = Boolean(
    preference?.meta.locked ||
      preference?.meta.is_read_only ||
      preference?.meta.read_only ||
      periodSettings?.finalized_at,
  )
  const deadline = formatDeadline(
    preference?.meta.deadline ?? periodSettings?.preference_deadline ?? null,
  )

  const beginEdit = () => {
    setDraft(slots.map((slot) => ({ ...slot })))
    setSaveError(null)
    setEditing(true)
  }

  const updateSlot = (index: number, patch: Partial<PreferenceSlot>) => {
    setDraft((current) =>
      current.map((slot, slotIndex) =>
        slotIndex === index ? { ...slot, ...patch } : slot,
      ),
    )
    setSaveError(null)
  }

  const addSlot = (kind: PreferenceSlot["kind"]) => {
    setDraft((current) => [
      ...current,
      { day_of_week: 1, start_time: "07:00", end_time: "08:00", kind },
    ])
    setSaveError(null)
  }

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validationError = validateSlots(draft)
    if (validationError) {
      setSaveError(validationError)
      return
    }
    setSaving(true)
    setSaveError(null)
    try {
      const response = await schedulingService.replaceMyPreferences({
        academic_period_id: periodId,
        slots: draft.map(({ day_of_week, start_time, end_time, kind }) => ({
          day_of_week,
          start_time,
          end_time,
          kind,
        })),
      })
      setPreference(response)
      setEditing(false)
      setNotice("Preferensi jadwal tersimpan.")
    } catch (cause) {
      setSaveError(
        apiErrorMessage(
          cause,
          "Preferensi gagal disimpan. Periksa rentang yang beririsan.",
        ),
      )
    } finally {
      setSaving(false)
    }
  }

  const requestCopy = () => {
    if (!previousPeriod) return
    setCopyError(null)
    setCopyTarget(previousPeriod)
  }

  const copyPreference = async () => {
    if (!copyTarget) return
    setCopying(true)
    setCopyError(null)
    try {
      const response = await schedulingService.copyMyPreferences({
        from_academic_period_id: copyTarget.academic_period_id,
        academic_period_id: periodId,
        overwrite: slots.length > 0,
      })
      setPreference(response)
      setEditing(false)
      setCopyTarget(null)
      setNotice(`Preferensi disalin dari ${copyTarget.label}.`)
    } catch (cause) {
      setCopyError(
        apiErrorMessage(cause, "Preferensi periode sebelumnya gagal disalin."),
      )
    } finally {
      setCopying(false)
    }
  }

  if (user?.role !== "lecturer") {
    return (
      <section className="rounded-xl border border-border bg-surface p-6">
        <h1 className="font-heading text-xl font-bold text-navy">
          Preferensi Jadwal
        </h1>
        <p className="mt-2 text-sm text-muted">
          Preferensi hanya dapat diisi oleh dosen untuk akunnya sendiri.
        </p>
      </section>
    )
  }

  return (
    <section
      aria-labelledby="preference-title"
      className="flex w-full flex-col gap-6"
    >
      <header>
        <h1
          id="preference-title"
          className="font-heading text-2xl font-bold text-navy"
        >
          Preferensi Jadwal
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Tentukan jam yang Anda utamakan dan blok waktu yang tidak dapat
          digunakan untuk mengajar.
        </p>
      </header>

      <div className="rounded-xl border border-border bg-surface p-4">
        {periodsLoading ? (
          <p role="status" className="mt-2 text-sm text-muted">
            Memuat periode akademik...
          </p>
        ) : periodsError ? (
          <div role="alert" className="mt-2 flex flex-wrap items-center gap-3">
            <span className="text-sm text-orange">{periodsError}</span>
            <button
              type="button"
              onClick={() => setPeriodReloadKey((key) => key + 1)}
              className={cn(
                buttonClass,
                "border border-border bg-surface text-navy hover:bg-accent",
              )}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" /> Coba lagi
            </button>
          </div>
        ) : periods.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            Belum ada periode akademik. Hubungi admin untuk menyiapkan periode.
          </p>
        ) : (
          <SearchableCombobox
            id="preference-period"
            label="Periode akademik"
            options={periods.map((period) => ({
              value: period.academic_period_id,
              label: period.label,
              hint: period.is_current ? "Aktif" : undefined,
            }))}
            value={periodId}
            onChange={setPeriodId}
            placeholder="Pilih periode"
            searchPlaceholder="Cari tahun atau semester"
            emptyLabel="Periode tidak ditemukan."
            disabled={editing || saving}
            className="mt-2 max-w-md"
          />
        )}
      </div>

      {!periodsLoading && !periodsError && periodId && (
        <>
          <section
            aria-labelledby="preference-deadline-title"
            className="rounded-xl border border-border bg-surface p-4"
          >
            <h2
              id="preference-deadline-title"
              className="text-sm font-bold text-navy"
            >
              Deadline Preferensi
            </h2>
            {settingsLoading ? (
              <p role="status" className="mt-1 text-sm text-muted">
                Memuat deadline...
              </p>
            ) : settingsError ? (
              <div
                role="alert"
                className="mt-2 flex flex-wrap items-center gap-3"
              >
                <span className="text-sm text-orange">{settingsError}</span>
                <button
                  type="button"
                  onClick={() => setSettingsReloadKey((key) => key + 1)}
                  className={cn(
                    buttonClass,
                    "border border-border bg-surface text-navy hover:bg-accent",
                  )}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" /> Coba lagi
                </button>
              </div>
            ) : deadline ? (
              <p className="mt-1 text-sm text-navy">
                Isi atau perbarui preferensi paling lambat{" "}
                <strong>{deadline}</strong>. Melewati deadline tidak mengunci
                edit sebelum jadwal final.
              </p>
            ) : (
              <p className="mt-1 text-sm text-muted">
                PJ Prodi atau admin belum menetapkan deadline. Anda dapat
                mengisi preferensi sebelum jadwal final.
              </p>
            )}
          </section>
          {locked && (
            <p
              role="status"
              className="rounded-lg border border-gold bg-gold/15 px-4 py-3 text-sm text-navy"
            >
              Preferensi terkunci karena jadwal periode ini sudah final.
            </p>
          )}
          {notice && (
            <p
              role="status"
              className="rounded-lg border border-border bg-accent px-4 py-3 text-sm text-navy"
            >
              {notice}
            </p>
          )}
          {loading && (
            <p
              role="status"
              className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-muted"
            >
              Memuat preferensi jadwal...
            </p>
          )}
          {!loading && loadError && (
            <div
              role="alert"
              className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="text-sm text-navy">{loadError}</span>
              <button
                type="button"
                onClick={() => setReloadKey((key) => key + 1)}
                className={cn(
                  buttonClass,
                  "border border-orange bg-surface text-orange hover:bg-orange/10",
                )}
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" /> Coba lagi
              </button>
            </div>
          )}

          {!loading && !loadError && preference && !editing && (
            <>
              <div className="rounded-xl border border-border bg-surface p-4 sm:p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="font-heading text-lg font-bold text-navy">
                      {slots.length > 0
                        ? "Ringkasan preferensi"
                        : "Belum ada preferensi"}
                    </h2>
                    <p className="mt-1 text-sm text-muted">
                      Status kelengkapan:{" "}
                      {preference.meta.completeness.filled
                        ? "terisi"
                        : "belum terisi"}
                      .{" "}
                      {slots.length > 0
                        ? `${preference.meta.completeness.preferred_count} jam preferensi dan ${preference.meta.completeness.unavailable_count} blok tidak tersedia.`
                        : "Tambahkan jam preferensi atau blok tidak tersedia untuk periode ini."}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={beginEdit}
                    disabled={locked}
                    className={cn(
                      buttonClass,
                      "border border-navy bg-navy text-white hover:bg-navy-light",
                    )}
                  >
                    <Pencil className="h-4 w-4" aria-hidden="true" />{" "}
                    {slots.length > 0 ? "Ubah preferensi" : "Isi preferensi"}
                  </button>
                </div>
                {slots.length === 0 ? (
                  <div className="mt-6 border-t border-border pt-6">
                    <p className="text-sm text-muted">
                      Preferensi kosong tidak menambah penalti. Anda tetap dapat
                      mengisinya sebelum jadwal final.
                    </p>
                  </div>
                ) : (
                  <div className="mt-6 grid gap-6 lg:grid-cols-2">
                    {([
                      ["preferred", "Jam Preferensi"],
                      ["unavailable", "Blok Tidak Tersedia"],
                    ] as const).map(([kind, title]) => (
                      <div key={kind}>
                        <h3 className="text-sm font-bold text-foreground">
                          {title}
                        </h3>
                        {slots.some((slot) => slot.kind === kind) ? (
                          <ul className="mt-3 divide-y divide-border rounded-lg border border-border">
                            {slots
                              .filter((slot) => slot.kind === kind)
                              .map((slot, index) => (
                                <li
                                  key={`${slot.day_of_week}-${slot.start_time}-${index}`}
                                  className="flex min-h-11 flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                                >
                                  <span>
                                    {slot.day_name ??
                                      DAYS[slot.day_of_week - 1]?.label}
                                  </span>
                                  <span className="font-mono text-navy">
                                    {slot.start_time} - {slot.end_time}
                                  </span>
                                </li>
                              ))}
                          </ul>
                        ) : (
                          <p className="mt-3 text-sm text-muted">
                            Belum ada {title.toLowerCase()}.
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {previousPeriod && (
                <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-muted">
                    Salin preferensi dari {previousPeriod.label}.
                  </p>
                  <button
                    type="button"
                    onClick={requestCopy}
                    disabled={locked || copying}
                    className={cn(
                      buttonClass,
                      "border border-border bg-surface text-navy hover:bg-accent",
                    )}
                  >
                    <Copy className="h-4 w-4" aria-hidden="true" /> Salin
                    periode sebelumnya
                  </button>
                </div>
              )}
              {preference.meta.warnings.length > 0 && (
                <section
                  aria-labelledby="preference-warning-title"
                  className="rounded-xl border border-orange/30 bg-orange/10 p-4"
                >
                  <h2
                    id="preference-warning-title"
                    className="flex items-center gap-2 text-sm font-bold text-navy"
                  >
                    <AlertCircle
                      className="h-4 w-4 text-orange"
                      aria-hidden="true"
                    />{" "}
                    Bentrok dengan kelas yang ditugaskan
                  </h2>
                  <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-navy">
                    {preference.meta.warnings.map((warning, index) => (
                      <li key={index}>{warningMessage(warning)}</li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}

          {!loading && !loadError && preference && editing && (
            <form
              onSubmit={save}
              noValidate
              className="rounded-xl border border-border bg-surface p-4 sm:p-6"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="font-heading text-lg font-bold text-navy">
                    Ubah preferensi
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    Rentang pada hari yang sama tidak boleh beririsan.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm text-muted">
                    Status: {locked ? "terkunci" : "dapat diedit"}
                  </span>
                  {previousPeriod && (
                    <button
                      type="button"
                      onClick={requestCopy}
                      disabled={saving || locked}
                      className={cn(
                        buttonClass,
                        "border border-border bg-surface text-navy hover:bg-accent",
                      )}
                    >
                      <Copy className="h-4 w-4" aria-hidden="true" /> Salin
                      periode sebelumnya
                    </button>
                  )}
                </div>
              </div>
              {saveError && (
                <p
                  role="alert"
                  className="mt-4 rounded-lg border border-orange/30 bg-orange/10 p-3 text-sm text-navy"
                >
                  {saveError}
                </p>
              )}
              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                {([
                  ["preferred", "Jam Preferensi"],
                  ["unavailable", "Blok Tidak Tersedia"],
                ] as const).map(([kind, title]) => (
                  <fieldset key={kind}>
                    <legend className="text-sm font-bold text-foreground">
                      {title}
                    </legend>
                    <div className="mt-3 flex flex-col gap-3">
                      {draft.map(
                        (slot, index) =>
                          slot.kind === kind && (
                            <div
                              key={index}
                              className="rounded-lg border border-border p-3"
                            >
                              <div className="grid gap-3 sm:grid-cols-3">
                                <label className="flex min-w-0 flex-col gap-1 text-xs font-semibold">
                                  Hari
                                  <select
                                    value={slot.day_of_week}
                                    onChange={(event) =>
                                      updateSlot(index, {
                                        day_of_week: Number(event.target.value),
                                      })
                                    }
                                    className={inputClass}
                                  >
                                    {DAYS.map((day) => (
                                      <option key={day.value} value={day.value}>
                                        {day.label}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                                <label className="flex min-w-0 flex-col gap-1 text-xs font-semibold">
                                  Mulai
                                  <select
                                    value={slot.start_time}
                                    onChange={(event) =>
                                      updateSlot(index, {
                                        start_time: event.target.value,
                                      })
                                    }
                                    className={inputClass}
                                  >
                                    {START_TIMES.map((time) => (
                                      <option key={time} value={time}>
                                        {time}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                                <label className="flex min-w-0 flex-col gap-1 text-xs font-semibold">
                                  Selesai
                                  <select
                                    value={slot.end_time}
                                    onChange={(event) =>
                                      updateSlot(index, {
                                        end_time: event.target.value,
                                      })
                                    }
                                    className={inputClass}
                                  >
                                    {END_TIMES.map((time) => (
                                      <option key={time} value={time}>
                                        {time}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                              </div>
                              <button
                                type="button"
                                onClick={() =>
                                  setDraft((current) =>
                                    current.filter(
                                      (_, slotIndex) => slotIndex !== index,
                                    ),
                                  )
                                }
                                className={cn(
                                  buttonClass,
                                  "mt-3 w-full border border-orange/40 text-orange hover:bg-orange/10",
                                )}
                              >
                                <Trash2
                                  className="h-4 w-4"
                                  aria-hidden="true"
                                />{" "}
                                Hapus {title.toLowerCase()}
                              </button>
                            </div>
                          ),
                      )}
                      <button
                        type="button"
                        onClick={() => addSlot(kind)}
                        className={cn(
                          buttonClass,
                          "border border-dashed border-navy text-navy hover:bg-accent",
                        )}
                      >
                        <Plus className="h-4 w-4" aria-hidden="true" /> Tambah{" "}
                        {title.toLowerCase()}
                      </button>
                    </div>
                  </fieldset>
                ))}
              </div>
              <div className="mt-6 flex flex-col-reverse gap-3 border-t border-border pt-4 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => {
                    setEditing(false)
                    setSaveError(null)
                  }}
                  className={cn(
                    buttonClass,
                    "border border-border bg-surface text-navy hover:bg-accent",
                  )}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={saving || locked}
                  className={cn(
                    buttonClass,
                    "border border-navy bg-navy text-white hover:bg-navy-light",
                  )}
                  aria-busy={saving}
                >
                  {saving ? "Menyimpan..." : "Simpan preferensi"}
                </button>
              </div>
            </form>
          )}
        </>
      )}

      {copyTarget && (
        <ConfirmDialog
          title="Salin preferensi periode sebelumnya?"
          body={
            <p className="text-sm text-muted">
              {slots.length > 0
                ? `Preferensi ${copyTarget.label} akan mengganti seluruh preferensi periode ini.`
                : `Preferensi ${copyTarget.label} akan disalin ke periode ini.`}
            </p>
          }
          confirmLabel="Salin preferensi"
          busy={copying}
          errorMessage={copyError}
          onCancel={() => {
            if (!copying) setCopyTarget(null)
          }}
          onConfirm={copyPreference}
        />
      )}
    </section>
  )
}
