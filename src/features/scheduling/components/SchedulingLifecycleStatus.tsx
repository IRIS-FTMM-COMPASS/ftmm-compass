import { cn } from "@/shared/utils"
import type {
  BoardClassItem,
  BoardProgramStatus,
  FinalizeResponse,
  GenerateResponse,
} from "../schedulingService"

interface SchedulingLifecycleStatusProps {
  staleCount: number
  inputRevision: number | null
  stalePrograms: BoardProgramStatus[]
  staleClasses: BoardClassItem[]
  generationResult: GenerateResponse | null
  finalizeResult: FinalizeResponse | null
  generationScopeLabel: string | null
}

const VISIBLE_STALE_CLASSES = 6
const VISIBLE_MISSING_USERS = 6

export default function SchedulingLifecycleStatus({
  staleCount,
  inputRevision,
  stalePrograms,
  staleClasses,
  generationResult,
  finalizeResult,
  generationScopeLabel,
}: SchedulingLifecycleStatusProps) {
  const hasStaleSchedule = staleCount > 0 || stalePrograms.length > 0
  const visibleStaleClasses = staleClasses.slice(0, VISIBLE_STALE_CLASSES)
  const hiddenStaleClassCount = staleClasses.length - visibleStaleClasses.length
  const missingUsers =
    finalizeResult?.completeness.preferences.missing_user_ids ?? []
  const visibleMissingUsers = missingUsers.slice(0, VISIBLE_MISSING_USERS)

  return (
    <>
      <section
        role="status"
        aria-live="polite"
        className={cn(
          "space-y-3 rounded-xl border p-4",
          hasStaleSchedule
            ? "border-gold/50 bg-gold/10"
            : "border-teal/40 bg-teal/10",
        )}
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <h2 className="font-heading text-base font-bold text-navy">
              {hasStaleSchedule
                ? "Jadwal stale, regenerasi diperlukan"
                : "Jadwal sesuai input terbaru"}
            </h2>
            <p className="text-xs text-navy">
              {hasStaleSchedule
                ? `${staleCount} kelas belum sesuai dengan input terbaru. Buat ulang jadwal sebelum finalisasi.`
                : `${staleCount} kelas stale pada data papan ini.`}
            </p>
          </div>
          {inputRevision !== null && (
            <p className="shrink-0 font-mono text-xs text-navy">
              Revisi input: {inputRevision}
            </p>
          )}
        </div>

        {stalePrograms.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold text-navy">
              Program studi terdampak
            </h3>
            <ul className="flex flex-wrap gap-2">
              {stalePrograms.map((program) => (
                <li
                  key={program.study_program_id}
                  className="rounded-md border border-gold/50 bg-surface px-2 py-1 text-xs text-navy"
                >
                  <span className="font-mono font-semibold">
                    {program.study_program_code || program.study_program_id}
                  </span>
                  {", "}
                  {program.label || "status program studi stale"}
                </li>
              ))}
            </ul>
          </div>
        )}

        {visibleStaleClasses.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-xs font-semibold text-navy">
              Kelas yang perlu dibuat ulang
            </h3>
            <ul className="divide-y divide-gold/30 rounded-lg border border-gold/40 bg-surface">
              {visibleStaleClasses.map((item) => (
                <li
                  key={item.class_section_id}
                  className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs"
                >
                  <span className="font-mono font-semibold text-navy">
                    {item.course_code || "Mata kuliah tanpa kode"}
                  </span>
                  <span className="text-muted">
                    {item.course_name}, kelas {item.section_code}
                  </span>
                </li>
              ))}
            </ul>
            {hiddenStaleClassCount > 0 && (
              <p className="text-xs text-navy">
                Dan {hiddenStaleClassCount} kelas stale lainnya pada tampilan
                ini.
              </p>
            )}
          </div>
        )}
      </section>

      {generationResult && (
        <section
          aria-labelledby="generation-result-title"
          className="space-y-3 rounded-xl border border-teal/40 bg-teal/10 p-4"
        >
          <div className="space-y-1">
            <h2
              id="generation-result-title"
              className="font-heading text-base font-bold text-navy"
            >
              Hasil pembuatan ulang jadwal
            </h2>
            <p className="text-xs text-muted">
              {generationResult.mode === "full_reset"
                ? "Reset penuh selesai"
                : "Regenerasi selesai"}
              {generationScopeLabel
                ? ` untuk ${generationScopeLabel}`
                : " untuk semua program studi draf"}
              {", revisi input "}
              {generationResult.input_revision}
            </p>
          </div>
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["Kelas dibuat ulang", generationResult.regenerated_count],
              ["Final dipertahankan", generationResult.preserved_final_count],
              ["Manual dipertahankan", generationResult.preserved_manual_count],
              ["Kelas ditempatkan", generationResult.assigned_count],
              ["Kelas belum terjadwal", generationResult.unassigned_count],
              ["Bentrok terdeteksi", generationResult.conflict_count],
            ].map(([label, value]) => (
              <div key={label} className="space-y-0.5">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="text-lg font-semibold tabular-nums text-navy">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {finalizeResult && (
        <section
          aria-labelledby="finalize-result-title"
          className="space-y-3 rounded-xl border border-navy/20 bg-surface p-4"
        >
          <div className="space-y-1">
            <h2
              id="finalize-result-title"
              className="font-heading text-base font-bold text-navy"
            >
              {finalizeResult.warnings.length > 0
                ? "Finalisasi selesai dengan catatan"
                : "Finalisasi selesai"}
            </h2>
            <p className="text-xs text-muted">
              {finalizeResult.all_final
                ? "Seluruh program studi telah final."
                : "Jadwal program studi ini telah final."}
            </p>
          </div>

          {finalizeResult.warnings.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-navy">
                Catatan tidak memblokir
              </h3>
              <ul className="space-y-2">
                {finalizeResult.warnings.map((warning, index) => (
                  <li
                    key={`${warning.code}-${warning.class_section_id ?? warning.user_id ?? index}`}
                    className="rounded-lg border border-gold/40 bg-gold/10 px-3 py-2 text-xs text-navy"
                  >
                    {warning.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <dl className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-0.5">
              <dt className="text-xs text-muted">Kelas terjadwal</dt>
              <dd className="text-sm font-semibold tabular-nums text-navy">
                {finalizeResult.completeness.classes.scheduled} dari{" "}
                {finalizeResult.completeness.classes.total}
              </dd>
            </div>
            <div className="space-y-0.5">
              <dt className="text-xs text-muted">Preferensi diterima</dt>
              <dd className="text-sm font-semibold tabular-nums text-navy">
                {finalizeResult.completeness.preferences.submitted} dari{" "}
                {finalizeResult.completeness.preferences.expected}
              </dd>
            </div>
          </dl>

          <p className="text-xs text-muted">
            {finalizeResult.completeness.preferences.complete
              ? "Seluruh preferensi dosen telah lengkap."
              : "Preferensi dosen belum lengkap. Kekurangan ini tidak membatalkan finalisasi."}
          </p>
          {visibleMissingUsers.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-navy">
                Dosen yang belum mengirim preferensi
              </h3>
              <ul className="flex flex-wrap gap-2">
                {visibleMissingUsers.map((userId) => (
                  <li
                    key={userId}
                    className="rounded-md border border-border bg-background px-2 py-1 font-mono text-xs break-all text-navy"
                  >
                    {userId}
                  </li>
                ))}
              </ul>
              {missingUsers.length > visibleMissingUsers.length && (
                <p className="text-xs text-muted">
                  Dan {missingUsers.length - visibleMissingUsers.length} dosen
                  lainnya.
                </p>
              )}
            </div>
          )}
        </section>
      )}
    </>
  )
}
