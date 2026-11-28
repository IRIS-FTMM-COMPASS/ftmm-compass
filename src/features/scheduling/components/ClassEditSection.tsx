import type { FormEvent } from "react"
import SearchableCombobox, {
  type ComboboxOption,
} from "@/shared/ui/SearchableCombobox"
import FormFieldError from "@/shared/ui/FormFieldError"
import type { ClassEditDraft } from "../hooks/useSchedulingActions"

const DAYS = [
  { day: 1, label: "Senin" },
  { day: 2, label: "Selasa" },
  { day: 3, label: "Rabu" },
  { day: 4, label: "Kamis" },
  { day: 5, label: "Jumat" },
] as const

const START_HOURS = Array.from({ length: 10 }, (_, index) => index + 7)

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

interface ClassEditSectionProps {
  draft: ClassEditDraft
  roomOptions: ComboboxOption[]
  busy: boolean
  roomError: string | null
  onChange: (draft: ClassEditDraft) => void
  onClearRoomError: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onRequestClose: () => void
}

export default function ClassEditSection({
  draft,
  roomOptions,
  busy,
  roomError,
  onChange,
  onClearRoomError,
  onSubmit,
  onRequestClose,
}: ClassEditSectionProps) {
  return (
    <section
      aria-labelledby="class-edit-title"
      className="rounded-xl border border-navy/20 bg-surface p-4"
    >
      <h3
        id="class-edit-title"
        className="font-heading text-base font-bold text-navy"
      >
        Ubah jadwal {draft.item.course_code}, {draft.item.section_code}
      </h3>
      <p className="mb-3 text-xs text-muted">
        {draft.item.course_name}, blok {draft.item.credits} jam
      </p>
      <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
          Hari
          <select
            value={draft.day_of_week}
            onChange={(event) =>
              onChange({ ...draft, day_of_week: Number(event.target.value) })
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
        <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
          Jam mulai
          <select
            value={draft.start_hour}
            onChange={(event) =>
              onChange({ ...draft, start_hour: Number(event.target.value) })
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
        <div className="flex flex-col gap-1">
          <SearchableCombobox
            id="class-edit-room"
            label="Ruangan"
            options={roomOptions}
            value={draft.room_id}
            onChange={(roomId) => {
              onChange({ ...draft, room_id: roomId })
              onClearRoomError()
            }}
            placeholder="Pilih ruangan"
            searchPlaceholder="Cari ruangan"
            emptyLabel="Tidak ada ruangan yang cocok."
            invalid={Boolean(roomError)}
            errorId={roomError ? "class-edit-room-error" : undefined}
          />
          <FormFieldError id="class-edit-room-error" message={roomError} />
        </div>
        <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
          Alasan perubahan *
          <input
            type="text"
            required
            maxLength={500}
            value={draft.reason}
            onChange={(event) =>
              onChange({ ...draft, reason: event.target.value })
            }
            placeholder="Contoh: menyesuaikan Preferensi Jadwal"
            className="min-h-11 rounded-lg border border-input bg-surface px-3 text-xs font-normal"
          />
        </label>
        <div className="flex items-end gap-2 md:col-span-4">
          <button
            type="submit"
            disabled={busy || draft.reason.trim().length === 0}
            className="min-h-11 rounded-lg bg-navy px-4 text-xs font-semibold text-white transition-colors hover:bg-navy-light disabled:opacity-60 cursor-pointer"
          >
            Simpan perubahan
          </button>
          <button
            type="button"
            onClick={onRequestClose}
            className="min-h-11 rounded-lg border border-border px-4 text-xs font-semibold text-navy transition-colors hover:bg-accent cursor-pointer"
          >
            Batal
          </button>
        </div>
      </form>
    </section>
  )
}
