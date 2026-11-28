import { cn } from "@/shared/utils"
import { LINTAS_PRODI_FILTER } from "./BoardGrid"
import type { ClassScope, SchedulingModel } from "../boardModel"
import type { SchedulingBusyAction } from "../hooks/useSchedulingActions"

interface SchedulingControlsProps {
  model: SchedulingModel
  selectedProgramId: string
  classScope: ClassScope
  busyAction: SchedulingBusyAction | null
  onSelectProgram: (programId: string) => void
  onSelectClassScope: (scope: ClassScope) => void
  onRegenerate: () => void
  onFullReset: () => void
  onFinalize: () => void
  onUnlock: () => void
}

export default function SchedulingControls({
  model,
  selectedProgramId,
  classScope,
  busyAction,
  onSelectProgram,
  onSelectClassScope,
  onRegenerate,
  onFullReset,
  onFinalize,
  onUnlock,
}: SchedulingControlsProps) {
  const {
    canOperateSchedule,
    isAdmin,
    isPjProdi,
    isOrdinaryLecturer,
    programs,
    programLabels,
    actorStudyProgramId,
    viewScopeLabel,
    actionScopeLabel,
    blockingConflictCount,
    scopedUnassigned,
    finalizeBlockers,
    isCurrentScopeFinal,
    isPeriodFinal,
    hasFinalProgram,
    periodId,
    unmappedRoomCount,
    unmappedLecturerCount,
    emptySectionCount,
  } = model

  return (
    <section
      aria-labelledby="scheduling-controls-title"
      className="space-y-3 rounded-xl border border-border bg-surface p-4"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h2
            id="scheduling-controls-title"
            className="font-heading text-base font-bold text-navy"
          >
            {canOperateSchedule ? "Kontrol Penjadwalan" : "Tampilan jadwal"}
          </h2>
        </div>
        <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-end">
          <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
            Filter program studi
            <select
              value={selectedProgramId}
              onChange={(event) => onSelectProgram(event.target.value)}
              className="min-h-11 rounded-lg border border-input bg-surface px-3 text-xs font-normal text-navy disabled:cursor-not-allowed disabled:bg-background"
            >
              <>
                <option value="">Semua program studi</option>
                <option value={LINTAS_PRODI_FILTER}>Lintas prodi</option>
                {programs.map((program) => {
                  const label = programLabels.get(program.study_program_id)
                  return (
                    <option
                      key={program.study_program_id}
                      value={program.study_program_id}
                    >
                      {[label?.code ?? program.study_program_code, label?.name]
                        .filter(Boolean)
                        .join(" ") || "Program studi"}
                    </option>
                  )
                })}
              </>
            </select>
          </label>
          {isOrdinaryLecturer && (
            <label className="flex flex-col gap-1 text-xs font-semibold text-navy">
              Cakupan kelas
              <select
                value={classScope}
                onChange={(event) =>
                  onSelectClassScope(event.target.value as ClassScope)
                }
                className="min-h-11 rounded-lg border border-input bg-surface px-3 text-xs font-normal text-navy"
              >
                <option value="all">Semua kelas</option>
                <option value="mine">Kelas Saya</option>
              </select>
            </label>
          )}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">
        {canOperateSchedule
          ? `Tampilan: ${viewScopeLabel}. Aksi penjadwalan draf: ${actionScopeLabel}. ${blockingConflictCount} bentrok ruang/dosen, ${scopedUnassigned.length} kelas belum terjadwal.`
          : "Pilih program studi atau Kelas Saya. Tampilan ini hanya-baca."}
      </p>

      {canOperateSchedule && (
        <>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
            <span>{unmappedRoomCount} ruangan belum dipetakan</span>
            <span>{unmappedLecturerCount} dosen belum dipetakan</span>
            <span>{emptySectionCount} kelas tanpa blok jadwal</span>
          </div>
          <ul
            aria-label="Status penjadwalan per program studi"
            className="flex flex-wrap gap-2"
          >
            {programs
              .filter(
                (program) =>
                  !isPjProdi ||
                  program.study_program_id === actorStudyProgramId,
              )
              .map((program) => {
                const isActorProgram =
                  actorStudyProgramId !== null &&
                  program.study_program_id === actorStudyProgramId
                return (
                  <li
                    key={program.study_program_id}
                    className={cn(
                      "inline-flex flex-wrap items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]",
                      isActorProgram
                        ? "border-navy/30 bg-navy/10 text-navy"
                        : "border-border text-muted",
                    )}
                  >
                    <span className="font-mono font-semibold">
                      {[
                        program.study_program_code,
                        programLabels.get(program.study_program_id)?.name,
                      ]
                        .filter(Boolean)
                        .join(" ") || "Program studi"}
                    </span>
                    <span>{program.label || program.state}</span>
                    <span className="font-semibold">
                      {program.state === "final" ? "final" : "draft"}
                    </span>
                    {program.is_stale && (
                      <span className="font-semibold text-orange">
                        Jadwal stale
                      </span>
                    )}
                    {isActorProgram && (
                      <span className="font-semibold text-navy">
                        Prodi Anda
                      </span>
                    )}
                  </li>
                )
              })}
          </ul>

          <div className="flex flex-wrap items-center gap-2">
            {!isCurrentScopeFinal && (
              <button
                type="button"
                onClick={onRegenerate}
                disabled={busyAction !== null || !periodId}
                className="inline-flex min-h-11 items-center rounded-lg bg-navy px-4 text-xs font-semibold text-white transition-colors hover:bg-navy-light disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
              >
                Buat ulang jadwal
              </button>
            )}
            {isAdmin && !isCurrentScopeFinal && (
              <button
                type="button"
                onClick={onFullReset}
                disabled={busyAction !== null || !periodId}
                className="inline-flex min-h-11 items-center rounded-lg border border-orange/40 px-4 text-xs font-semibold text-orange transition-colors hover:bg-orange/10 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
              >
                Reset &amp; generate ulang
              </button>
            )}
            {isPjProdi && !isCurrentScopeFinal && (
              <>
                <button
                  type="button"
                  onClick={onFinalize}
                  disabled={
                    busyAction !== null ||
                    !periodId ||
                    finalizeBlockers.length > 0
                  }
                  className="inline-flex min-h-11 items-center rounded-lg bg-gold px-4 text-xs font-semibold text-navy-dark transition-colors hover:bg-gold-hover disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
                >
                  Finalisasi jadwal
                </button>
                <p
                  role="status"
                  className="w-full text-xs text-muted sm:w-auto"
                >
                  {finalizeBlockers.length > 0
                    ? `Finalisasi diblokir: ${finalizeBlockers.join(", ")}.`
                    : "Siap difinalisasi. Tidak ada blocker pada cakupan prodi ini."}
                </p>
              </>
            )}
            {isAdmin && (isPeriodFinal || hasFinalProgram) && (
              <button
                type="button"
                onClick={onUnlock}
                disabled={busyAction !== null || !periodId}
                className="inline-flex min-h-11 items-center rounded-lg border border-navy/30 px-4 text-xs font-semibold text-navy transition-colors hover:bg-accent disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold cursor-pointer disabled:cursor-not-allowed"
              >
                Buka kunci jadwal
              </button>
            )}
            {isCurrentScopeFinal && !isAdmin && (
              <p className="text-xs text-muted">
                Jadwal sudah final. Perubahan memerlukan pembukaan kunci oleh
                admin.
              </p>
            )}
          </div>
        </>
      )}
    </section>
  )
}
