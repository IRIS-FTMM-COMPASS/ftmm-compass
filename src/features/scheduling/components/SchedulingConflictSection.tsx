import { conflictMarkerLabel } from "./BoardGrid"
import type { VisibleConflictRow } from "../boardModel"

interface SchedulingConflictSectionProps {
  rows: VisibleConflictRow[]
}

export default function SchedulingConflictSection({
  rows,
}: SchedulingConflictSectionProps) {
  return (
    <section aria-labelledby="conflict-list-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2
          id="conflict-list-title"
          className="font-heading text-base font-bold text-navy"
        >
          Bentrok Jadwal
        </h2>
        <span className="rounded-full border border-danger/40 bg-danger/10 px-2.5 py-1 text-[11px] font-semibold text-danger">
          {rows.length} bentrok
        </span>
      </div>
      {rows.length === 0 ? (
        <p
          role="status"
          className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-3 text-xs text-navy"
        >
          Tidak ada bentrok ruang/dosen.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-xl border border-danger/30 bg-surface">
          {rows.map((row) => (
            <li
              key={row.key}
              className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs"
            >
              <div className="min-w-0 space-y-1">
                <p className="font-semibold text-navy">
                  {conflictMarkerLabel(row.conflict)}
                </p>
                {row.conflict.object_label && (
                  <p className="text-muted">{row.conflict.object_label}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {rows.length > 0 && (
        <p className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted">
          Hubungi PJ Prodi melalui kanal resmi untuk menindaklanjuti bentrok.
          Aplikasi tidak menyediakan kontak atau rekomendasi dosen.
        </p>
      )}
    </section>
  )
}
