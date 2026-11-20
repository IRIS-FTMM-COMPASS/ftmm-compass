import { useEffect, useRef, useState } from "react"
import { AlertCircle, Plus } from "lucide-react"
import { useSession } from "@/features/auth/session"
import { cn } from "@/shared/utils"
import { apiErrorMessage } from "@/shared/api/client"
import {
  schedulingService,
  type AvailabilityLecturerResponse,
  type AvailabilityResponse,
  type AvailabilitySlotRequest,
} from "../schedulingService"

const DAYS = [
  { day: 1, label: "Senin" },
  { day: 2, label: "Selasa" },
  { day: 3, label: "Rabu" },
  { day: 4, label: "Kamis" },
  { day: 5, label: "Jumat" },
] as const

const START_HOURS = Array.from({ length: 10 }, (_, index) => index + 7)

interface SlotDraft {
  key: string
  day_of_week: number
  start_hour: number
  end_hour: number
}

function toDraft(slot: AvailabilityResponse, key: string): SlotDraft {
  return {
    key,
    day_of_week: slot.day_of_week,
    start_hour: slot.start_hour,
    end_hour: slot.end_hour,
  }
}

function signature(slots: AvailabilitySlotRequest[]): string {
  return slots
    .map((slot) => `${slot.day_of_week}-${slot.start_hour}-${slot.end_hour}`)
    .sort()
    .join("|")
}

function validateSlots(slots: AvailabilitySlotRequest[]): string | null {
  const byDay = new Map<number, AvailabilitySlotRequest[]>()
  slots.forEach((slot) => {
    const daySlots = byDay.get(slot.day_of_week) ?? []
    daySlots.push(slot)
    byDay.set(slot.day_of_week, daySlots)
  })
  for (const [day, daySlots] of byDay) {
    const sorted = [...daySlots].sort((a, b) => a.start_hour - b.start_hour)
    for (let index = 1; index < sorted.length; index += 1) {
      if (sorted[index].start_hour < sorted[index - 1].end_hour) {
        const dayLabel =
          DAYS.find((item) => item.day === day)?.label ?? `hari ke-${day}`
        return `Slot pada ${dayLabel} saling bertabrakan. Geser salah satu jamnya.`
      }
    }
  }
  return null
}

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

function AvailabilitySelfEditor() {
  const { user } = useSession()
  const isLecturer = user?.role === "lecturer"

  const [savedSlots, setSavedSlots] = useState<AvailabilityResponse[]>([])
  const [drafts, setDrafts] = useState<SlotDraft[]>([])
  const [isLoading, setIsLoading] = useState(isLecturer)
  const [isSaving, setIsSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [notice, setNotice] = useState<string | null>(null)
  const keyCounter = useRef(0)

  useEffect(() => {
    if (!isLecturer) return
    let active = true
    setIsLoading(true)
    setLoadError(null)
    schedulingService
      .getMyAvailability()
      .then((items) => {
        if (!active) return
        setSavedSlots(items)
        setDrafts(
          items.map((item) => {
            keyCounter.current += 1
            return toDraft(item, `slot-${keyCounter.current}`)
          }),
        )
      })
      .catch((cause) => {
        if (active) {
          setLoadError(
            apiErrorMessage(cause, "Ketersediaan dosen tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [isLecturer, retryKey])

  if (!isLecturer) {
    return (
      <section aria-labelledby="availability-title" className="space-y-2">
        <h3
          id="availability-title"
          className="font-heading text-base font-bold text-navy"
        >
          Ketersediaan Dosen
        </h3>
        <p
          role="status"
          className="rounded-xl border border-border bg-background px-4 py-3 text-xs text-muted"
        >
          Ketersediaan mengajar diisi oleh dosen melalui akun masing-masing.
          Akun Anda tidak memiliki hak untuk mengatur slot ini.
        </p>
      </section>
    )
  }

  const payload: AvailabilitySlotRequest[] = drafts.map((draft) => ({
    day_of_week: draft.day_of_week,
    start_hour: draft.start_hour,
    end_hour: draft.end_hour,
  }))
  const validationError = validateSlots(payload)
  const savedSignature = signature(
    savedSlots.map((slot) => ({
      day_of_week: slot.day_of_week,
      start_hour: slot.start_hour,
      end_hour: slot.end_hour,
    })),
  )
  const isDirty = signature(payload) !== savedSignature

  const updateDraft = (key: string, changes: Partial<SlotDraft>) => {
    setActionError(null)
    setNotice(null)
    setDrafts((current) =>
      current.map((draft) => {
        if (draft.key !== key) return draft
        const next = { ...draft, ...changes }
        if (next.end_hour <= next.start_hour) {
          next.end_hour = Math.min(next.start_hour + 1, 17)
        }
        return next
      }),
    )
  }

  const addSlot = () => {
    setActionError(null)
    setNotice(null)
    keyCounter.current += 1
    setDrafts((current) => [
      ...current,
      {
        key: `slot-${keyCounter.current}`,
        day_of_week: 1,
        start_hour: 8,
        end_hour: 10,
      },
    ])
  }

  const saveSlots = async () => {
    if (validationError || !isDirty || isSaving) return
    setIsSaving(true)
    setActionError(null)
    setNotice(null)
    try {
      const saved = await schedulingService.saveMyAvailability(payload)
      setSavedSlots(saved)
      setDrafts(
        saved.map((item) => {
          keyCounter.current += 1
          return toDraft(item, `slot-${keyCounter.current}`)
        }),
      )
      setNotice("Ketersediaan mengajar berhasil disimpan.")
    } catch (cause) {
      setActionError(
        apiErrorMessage(cause, "Ketersediaan mengajar gagal disimpan."),
      )
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section aria-labelledby="availability-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="space-y-1">
          <h3
            id="availability-title"
            className="font-heading text-base font-bold text-navy"
          >
            Ketersediaan Dosen
          </h3>
          <p className="text-xs text-muted">
            Tentukan jam saat dosen tersedia menerima Kelas MK. Satu SKS memakai
            satu blok jam penuh.
          </p>
        </div>
        <button
          type="button"
          onClick={addSlot}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-navy/25 bg-surface px-3 text-xs font-semibold text-navy transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          Tambah slot
        </button>
      </div>

      {isLoading && (
        <p role="status" className="text-xs text-muted">
          Memuat ketersediaan mengajar...
        </p>
      )}

      {!isLoading && loadError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-navy"
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
            onClick={() => setRetryKey((key) => key + 1)}
            className="min-h-11 rounded-lg border border-orange/40 px-3 font-semibold text-orange transition-colors hover:bg-orange/20 cursor-pointer"
          >
            Muat ulang
          </button>
        </div>
      )}

      {!isLoading && !loadError && drafts.length === 0 && (
        <p
          role="status"
          className="rounded-xl border border-border bg-background px-4 py-3 text-xs text-muted"
        >
          Belum ada slot ketersediaan. Tambahkan slot agar solver dapat
          menempatkan kelas pada jam tersebut.
        </p>
      )}

      {!isLoading && !loadError && drafts.length > 0 && (
        <div className="space-y-2">
          {drafts.map((draft, index) => (
            <div
              key={draft.key}
              className="grid gap-2 rounded-xl border border-border bg-surface p-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end"
            >
              <label className="flex flex-col gap-1 text-[11px] font-semibold text-navy">
                Hari
                <select
                  value={draft.day_of_week}
                  onChange={(event) =>
                    updateDraft(draft.key, {
                      day_of_week: Number(event.target.value),
                    })
                  }
                  className="min-h-11 rounded-lg border border-input bg-surface px-2 text-xs font-normal"
                >
                  {DAYS.map((day) => (
                    <option key={day.day} value={day.day}>
                      {day.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-semibold text-navy">
                Mulai
                <select
                  value={draft.start_hour}
                  onChange={(event) =>
                    updateDraft(draft.key, {
                      start_hour: Number(event.target.value),
                    })
                  }
                  className="min-h-11 rounded-lg border border-input bg-surface px-2 text-xs font-normal"
                >
                  {START_HOURS.map((hour) => (
                    <option key={hour} value={hour}>
                      {formatHour(hour)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-semibold text-navy">
                Sampai
                <select
                  value={draft.end_hour}
                  onChange={(event) =>
                    updateDraft(draft.key, {
                      end_hour: Number(event.target.value),
                    })
                  }
                  className="min-h-11 rounded-lg border border-input bg-surface px-2 text-xs font-normal"
                >
                  {Array.from(
                    { length: 17 - draft.start_hour },
                    (_, offset) => draft.start_hour + offset + 1,
                  ).map((hour) => (
                    <option key={hour} value={hour}>
                      {formatHour(hour)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => {
                  setActionError(null)
                  setNotice(null)
                  setDrafts((current) =>
                    current.filter((item) => item.key !== draft.key),
                  )
                }}
                aria-label={`Hapus slot ${index + 1}`}
                className="min-h-11 rounded-lg border border-orange/40 px-3 text-xs font-semibold text-orange transition-colors hover:bg-orange/10 cursor-pointer"
              >
                Hapus
              </button>
            </div>
          ))}
        </div>
      )}

      {validationError && (
        <p role="alert" className="text-xs font-semibold text-orange">
          {validationError}
        </p>
      )}
      {actionError && (
        <p role="alert" className="text-xs font-semibold text-orange">
          {actionError}
        </p>
      )}
      {notice && (
        <p role="status" className="text-xs font-semibold text-navy">
          {notice}
        </p>
      )}

      {!isLoading && !loadError && isDirty && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void saveSlots()}
            disabled={isSaving || Boolean(validationError)}
            className="inline-flex min-h-11 items-center rounded-lg bg-navy px-4 text-xs font-semibold text-white transition-colors hover:bg-navy-light disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed"
          >
            Simpan ketersediaan
          </button>
          <button
            type="button"
            onClick={() => {
              setActionError(null)
              setNotice(null)
              setDrafts(
                savedSlots.map((slot) => {
                  keyCounter.current += 1
                  return toDraft(slot, `slot-${keyCounter.current}`)
                }),
              )
            }}
            className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-xs font-semibold text-navy transition-colors hover:bg-accent cursor-pointer"
          >
            Batalkan perubahan
          </button>
        </div>
      )}

      <p className="text-[11px] text-muted">
        Perubahan tersimpan memengaruhi penjadwalan pada periode akademik aktif.
      </p>
    </section>
  )
}

function lecturerOptionLabel(lecturer: AvailabilityLecturerResponse): string {
  const name = lecturer.full_name?.trim() || lecturer.user_id
  const program = lecturer.study_program_code?.trim()
  return program ? `${name} · ${program}` : name
}

function AvailabilityInspector() {
  const [lecturers, setLecturers] = useState<AvailabilityLecturerResponse[]>([])
  const [selectedUserId, setSelectedUserId] = useState("")
  const [slots, setSlots] = useState<AvailabilityResponse[]>([])
  const [isLoadingLecturers, setIsLoadingLecturers] = useState(true)
  const [lecturersError, setLecturersError] = useState<string | null>(null)
  const [isLoadingSlots, setIsLoadingSlots] = useState(false)
  const [slotsError, setSlotsError] = useState<string | null>(null)
  const [lecturerReloadKey, setLecturerReloadKey] = useState(0)
  const [slotReloadKey, setSlotReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    setIsLoadingLecturers(true)
    setLecturersError(null)
    schedulingService
      .listAvailabilityLecturers()
      .then((items) => {
        if (!active) return
        setLecturers(items)
        setSelectedUserId((current) =>
          items.some((item) => item.user_id === current)
            ? current
            : (items[0]?.user_id ?? ""),
        )
      })
      .catch((cause) => {
        if (!active) return
        setLecturers([])
        setSelectedUserId("")
        setLecturersError(
          apiErrorMessage(cause, "Daftar dosen tidak dapat dimuat."),
        )
      })
      .finally(() => {
        if (active) setIsLoadingLecturers(false)
      })
    return () => {
      active = false
    }
  }, [lecturerReloadKey])

  useEffect(() => {
    if (!selectedUserId) {
      setSlots([])
      setSlotsError(null)
      setIsLoadingSlots(false)
      return
    }
    let active = true
    setIsLoadingSlots(true)
    setSlotsError(null)
    schedulingService
      .getLecturerAvailability(selectedUserId)
      .then((items) => {
        if (active) setSlots(items)
      })
      .catch((cause) => {
        if (!active) return
        setSlots([])
        setSlotsError(
          apiErrorMessage(cause, "Ketersediaan dosen tidak dapat dimuat."),
        )
      })
      .finally(() => {
        if (active) setIsLoadingSlots(false)
      })
    return () => {
      active = false
    }
  }, [selectedUserId, slotReloadKey])

  const slotsByDay = DAYS.map((day) => ({
    ...day,
    slots: slots
      .filter((slot) => slot.day_of_week === day.day)
      .sort((a, b) => a.start_hour - b.start_hour),
  }))
  const selectedLecturer = lecturers.find(
    (item) => item.user_id === selectedUserId,
  )

  return (
    <section aria-labelledby="availability-title" className="space-y-3">
      <div className="space-y-1">
        <h3
          id="availability-title"
          className="font-heading text-base font-bold text-navy"
        >
          Ketersediaan Dosen
        </h3>
        <p className="text-xs text-muted">
          Lihat ketersediaan mengajar dosen. Tampilan ini hanya untuk membaca;
          perubahan dilakukan melalui akun dosen yang bersangkutan.
        </p>
      </div>

      {isLoadingLecturers && (
        <p role="status" className="text-xs text-muted">
          Memuat daftar dosen...
        </p>
      )}

      {!isLoadingLecturers && lecturersError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-navy"
        >
          <span className="flex items-center gap-2">
            <AlertCircle
              className="h-4 w-4 shrink-0 text-orange"
              aria-hidden="true"
            />
            {lecturersError}
          </span>
          <button
            type="button"
            onClick={() => setLecturerReloadKey((key) => key + 1)}
            className="min-h-11 rounded-lg border border-orange/40 px-3 font-semibold text-orange transition-colors hover:bg-orange/20 cursor-pointer"
          >
            Muat ulang
          </button>
        </div>
      )}

      {!isLoadingLecturers && !lecturersError && lecturers.length === 0 && (
        <p
          role="status"
          className="rounded-xl border border-border bg-background px-4 py-3 text-xs text-muted"
        >
          Belum ada dosen yang dapat ditampilkan.
        </p>
      )}

      {!isLoadingLecturers && !lecturersError && lecturers.length > 0 && (
        <div className="space-y-1.5">
          <label
            htmlFor="availability-lecturer"
            className="block text-xs font-semibold text-navy"
          >
            Dosen
          </label>
          <select
            id="availability-lecturer"
            value={selectedUserId}
            onChange={(event) => setSelectedUserId(event.target.value)}
            aria-describedby="availability-lecturer-help"
            className="min-h-11 w-full rounded-lg border border-input bg-surface px-2 text-xs font-normal sm:w-96"
          >
            {lecturers.map((lecturer) => (
              <option key={lecturer.user_id} value={lecturer.user_id}>
                {lecturerOptionLabel(lecturer)}
              </option>
            ))}
          </select>
          <p id="availability-lecturer-help" className="text-[11px] text-muted">
            {selectedLecturer
              ? `Kode program studi: ${selectedLecturer.study_program_code || "-"}.`
              : "Pilih dosen untuk melihat ketersediaannya."}
          </p>
        </div>
      )}

      {selectedUserId && (
        <div className="space-y-2">
          <h4 className="font-heading text-sm font-bold text-navy">
            Ketersediaan mingguan
          </h4>

          {isLoadingSlots && (
            <p role="status" className="text-xs text-muted">
              Memuat ketersediaan dosen...
            </p>
          )}

          {!isLoadingSlots && slotsError && (
            <div
              role="alert"
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-navy"
            >
              <span className="flex items-center gap-2">
                <AlertCircle
                  className="h-4 w-4 shrink-0 text-orange"
                  aria-hidden="true"
                />
                {slotsError}
              </span>
              <button
                type="button"
                onClick={() => setSlotReloadKey((key) => key + 1)}
                className="min-h-11 rounded-lg border border-orange/40 px-3 font-semibold text-orange transition-colors hover:bg-orange/20 cursor-pointer"
              >
                Muat ulang
              </button>
            </div>
          )}

          {!isLoadingSlots && !slotsError && slots.length === 0 && (
            <p
              role="status"
              className="rounded-xl border border-border bg-background px-4 py-3 text-xs text-muted"
            >
              Dosen ini belum memiliki slot ketersediaan.
            </p>
          )}

          {!isLoadingSlots && !slotsError && slots.length > 0 && (
            <div
              role="list"
              aria-label={`Ketersediaan mingguan ${
                selectedLecturer?.full_name ?? "dosen terpilih"
              }`}
              className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3"
            >
              {slotsByDay.map((day) => (
                <div
                  key={day.day}
                  role="listitem"
                  className={cn(
                    "rounded-xl border bg-background px-3 py-2",
                    day.slots.length > 0 ? "border-navy/20" : "border-border",
                  )}
                >
                  <p className="font-heading text-xs font-semibold text-navy">
                    {day.label}
                  </p>
                  {day.slots.length === 0 ? (
                    <p className="mt-1 text-[11px] text-muted">
                      Tidak ada slot.
                    </p>
                  ) : (
                    <ul className="mt-1 space-y-1">
                      {day.slots.map((slot) => (
                        <li
                          key={slot.availability_id}
                          className="font-mono text-[11px] text-foreground"
                        >
                          {formatHour(slot.start_hour)} -{" "}
                          {formatHour(slot.end_hour)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

export default function AvailabilityPanel() {
  const { user } = useSession()
  const isAdmin = user?.role === "admin"
  const isPjProdi =
    user?.role === "lecturer" && user.is_program_coordinator === true

  if (isPjProdi || isAdmin) return <AvailabilityInspector />
  return <AvailabilitySelfEditor />
}
