import { ChevronLeft, ChevronRight } from "lucide-react"
import { SEMESTERS, isOddSemester } from "@/shared/domain/academics"

interface SemesterSwitcherProps {
  id: string
  value: number
  counts: Record<number, number>
  onChange: (semester: number) => void
}

export default function SemesterSwitcher({
  id,
  value,
  counts,
  onChange,
}: SemesterSwitcherProps) {
  return (
    <div className="flex items-center gap-2 md:hidden">
      <button
        type="button"
        aria-label="Semester sebelumnya"
        disabled={value <= SEMESTERS[0]}
        onClick={() => onChange(value - 1)}
        className="min-h-11 min-w-11 flex items-center justify-center rounded-lg border border-border bg-surface text-navy hover:bg-navy/5 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
      >
        <ChevronLeft className="w-5 h-5" />
      </button>
      <label htmlFor={id} className="sr-only">
        Pilih semester yang ditampilkan
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="min-h-11 min-w-0 flex-1 px-3 rounded-lg border border-border bg-surface text-xs font-semibold text-navy cursor-pointer"
      >
        {SEMESTERS.map((sem) => (
          <option key={sem} value={sem}>
            Semester {sem} · {isOddSemester(sem) ? "Ganjil" : "Genap"} ·{" "}
            {counts[sem] ?? 0} matkul
          </option>
        ))}
      </select>
      <button
        type="button"
        aria-label="Semester berikutnya"
        disabled={value >= SEMESTERS[SEMESTERS.length - 1]}
        onClick={() => onChange(value + 1)}
        className="min-h-11 min-w-11 flex items-center justify-center rounded-lg border border-border bg-surface text-navy hover:bg-navy/5 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
      >
        <ChevronRight className="w-5 h-5" />
      </button>
    </div>
  )
}
