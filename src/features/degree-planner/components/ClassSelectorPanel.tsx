import {
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Clock,
  MapPin,
  RotateCcw,
} from "lucide-react"
import { cn } from "@/shared/utils"
import { CourseOffering, formatTime } from "@/shared/domain/models"
import type {
  ScheduleConflictDetail,
  ScheduleValidationResult,
  SectionAlternative,
} from "@/shared/domain/timetable"
import { PlacedCourse } from "@/features/degree-planner/types"
import type { ReloadableResource } from "@/features/degree-planner/state/useReloadableFetch"

interface ClassSelectorPanelProps {
  activeSemester: number
  semesterCourses: PlacedCourse[]
  offerings: CourseOffering[]
  selectedSections: Record<string, string>
  onSelectSection: (courseId: string, sectionId: string) => void
  conflicts: ScheduleConflictDetail[]
  validationState: ReloadableResource<ScheduleValidationResult>
  onApplyAlternative: (alternative: SectionAlternative) => void
  onAutoResolveConflicts?: () => void
  periodLabel: string
  sectionsState: Pick<ReloadableResource<unknown>, "status" | "error" | "reload">
  scheduleIsFinal?: boolean
}

export default function ClassSelectorPanel({
  activeSemester,
  semesterCourses,
  offerings,
  selectedSections,
  onSelectSection,
  conflicts,
  validationState,
  onApplyAlternative,
  onAutoResolveConflicts,
  periodLabel,
  sectionsState,
  scheduleIsFinal = true,
}: ClassSelectorPanelProps) {
  const alternatives = validationState.data?.alternatives ?? []
  const validationError = validationState.error
  const sectionsStatus = sectionsState.status
  const sectionsError = sectionsState.error
  const conflictingCourseIds = new Set<string>()
  conflicts.forEach((conflict) => {
    conflictingCourseIds.add(conflict.courseACode)
    conflictingCourseIds.add(conflict.courseBCode)
  })

  const totalCredits = semesterCourses.reduce((sum, c) => sum + c.credits, 0)
  const selectedCount = semesterCourses.filter((c) =>
    Boolean(selectedSections[c.id]),
  ).length

  return (
    <div className="bg-surface rounded-2xl border border-border shadow-xs p-4 sm:p-5 flex flex-col h-full">
      <div className="pb-4 border-b border-border/70 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-navy" />
            <h3 className="font-heading font-bold text-base text-navy">
              Pilihan Kelas Semester {activeSemester}
            </h3>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-full bg-navy/8 text-navy border border-navy/15">
              {totalCredits} SKS Total
            </span>
          </div>
          <p className="text-xs text-muted mt-1">
            Pilih section kelas perkuliahan aktif untuk menata jadwal mingguan
            dan mencegah bentrok.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {conflicts.length > 0 ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-danger/10 text-danger border border-danger/25">
                <AlertTriangle className="w-3.5 h-3.5" />
                {conflicts.length} Bentrok Jadwal
              </span>
              {onAutoResolveConflicts && alternatives.length > 0 && (
                <button
                  type="button"
                  onClick={onAutoResolveConflicts}
                  disabled={!scheduleIsFinal}
                  className="min-h-11 min-w-11 px-2.5 text-xs font-semibold rounded-lg bg-navy text-white hover:bg-navy-light transition-colors flex items-center justify-center gap-1 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-navy"
                  title="Pilih kombinasi kelas yang tidak bentrok secara otomatis"
                >
                  <RotateCcw className="w-3 h-3 text-gold" />
                  Auto-Resolve
                </button>
              )}
            </div>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-teal/15 text-navy border border-teal/30">
              <CheckCircle2 className="w-3.5 h-3.5 text-teal" />
              Bebas Bentrok
            </span>
          )}
        </div>
      </div>

      {conflicts.length > 0 && (
        <div
          role="alert"
          className="mb-3 rounded-xl border border-danger/40 bg-danger/10 p-3"
        >
          <div className="flex items-center gap-2 text-xs font-bold text-danger">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            Bentrok Jadwal Terdeteksi
          </div>
          <ul className="mt-2 space-y-1.5">
            {conflicts.map((conflict, index) => (
              <li
                key={`${conflict.courseACode}-${conflict.sectionACode}-${conflict.courseBCode}-${conflict.sectionBCode}-${index}`}
                className="text-[11px] leading-snug text-foreground"
              >
                <span className="font-semibold text-danger">
                  {conflict.courseAName} ({conflict.courseACode} ·{" "}
                  {conflict.sectionACode})
                </span>{" "}
                bentrok dengan{" "}
                <span className="font-semibold text-danger">
                  {conflict.courseBName} ({conflict.courseBCode} ·{" "}
                  {conflict.sectionBCode})
                </span>{" "}
                pada <strong>{conflict.day}</strong>,{" "}
                <strong>
                  {conflict.start}–{conflict.end}
                </strong>
                .
              </li>
            ))}
          </ul>
        </div>
      )}

      {validationError && (
        <div
          role="alert"
          className="mb-3 rounded-xl border border-orange/40 bg-orange/10 p-3"
        >
          <p className="text-xs font-semibold text-navy">
            Validasi bentrok gagal dimuat
          </p>
          <p className="mt-1 text-[11px] text-foreground">{validationError}</p>
          <button
            type="button"
            onClick={validationState.reload}
            className="mt-2 min-h-11 px-3 rounded-lg bg-navy text-white text-xs font-semibold cursor-pointer hover:bg-navy-light focus-visible:outline-2 focus-visible:outline-navy focus-visible:outline-offset-2"
          >
            Coba validasi ulang
          </button>
        </div>
      )}

      {conflicts.length > 0 && (
        <section className="mb-3 rounded-xl border border-teal/40 bg-teal/5 p-3">
          <div className="flex items-center gap-2 text-xs font-bold text-navy">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-teal" />
            Alternatif Bebas Bentrok
          </div>
          {alternatives.length === 0 ? (
            <p className="mt-1.5 text-[11px] text-foreground">
              Belum ada kelas paralel bebas bentrok untuk kombinasi ini. Ubah
              section kelas lain atau periksa kembali setelah jadwal
              diterbitkan.
            </p>
          ) : (
            <div className="mt-2 space-y-2">
              {alternatives.map((alternative) => (
                <div
                  key={`${alternative.courseCode}-${alternative.section.sectionId}`}
                  className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-2.5 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-navy break-words">
                      {alternative.courseName} ({alternative.courseCode})
                    </p>
                    <p className="mt-0.5 text-[11px] text-foreground">
                      Section {alternative.section.sectionCode}
                      {alternative.section.schedules.map((slot, index) => (
                        <span key={`${slot.dayOfWeek}-${slot.start}-${index}`}>
                          {" · "}
                          {slot.day}, {formatTime(slot.start)}–
                          {formatTime(slot.end)}
                        </span>
                      ))}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onApplyAlternative(alternative)}
                    disabled={!scheduleIsFinal}
                    className="min-h-11 px-3 rounded-lg bg-teal text-white text-xs font-semibold cursor-pointer hover:bg-navy focus-visible:outline-2 focus-visible:outline-navy focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-teal"
                  >
                    Terapkan Solusi
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="flex-1 overflow-y-auto py-3 space-y-3.5 pr-0.5">
        {!scheduleIsFinal && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-lg border border-orange/40 bg-orange/10 px-3 py-2 text-xs font-semibold text-navy"
          >
            <Clock className="w-4 h-4 flex-shrink-0 text-orange" />
            Jadwal masih dalam proses
          </div>
        )}
        {semesterCourses.length === 0 ? (
          <div className="h-40 flex flex-col items-center justify-center text-center p-4 border border-dashed border-border rounded-xl">
            <Calendar className="w-8 h-8 text-muted/40 mb-2" />
            <p className="text-xs font-medium text-navy">
              Belum ada mata kuliah di Semester {activeSemester}
            </p>
            <p className="text-[11px] text-muted mt-0.5">
              Tambahkan matkul di tab Roadmap Studi terlebih dahulu.
            </p>
          </div>
        ) : sectionsStatus === "loading" ? (
          <div
            role="status"
            className="h-40 flex flex-col items-center justify-center text-center p-4 border border-dashed border-border rounded-xl"
          >
            <Clock className="w-8 h-8 text-muted/40 mb-2" />
            <p className="text-xs font-medium text-navy">
              Memuat jadwal kelas untuk {periodLabel}
            </p>
            <p className="text-[11px] text-muted mt-0.5">
              Data section diambil dari akademik untuk setiap mata kuliah.
            </p>
          </div>
        ) : sectionsStatus === "error" ? (
          <div
            role="alert"
            className="p-4 border border-danger/30 bg-danger/5 rounded-xl"
          >
            <div className="flex items-center gap-2 text-danger">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <p className="text-xs font-semibold">Jadwal kelas gagal dimuat</p>
            </div>
            <p className="text-[11px] text-foreground mt-1.5">
              {sectionsError ?? "Data akademik tidak merespons."} Coba kembali
              setelah koneksi pulih.
            </p>
            <button
              type="button"
              onClick={sectionsState.reload}
              className="mt-3 min-h-11 px-3 text-xs font-semibold rounded-lg bg-navy text-white hover:bg-navy-light transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-navy focus-visible:outline-offset-2"
            >
              Coba muat ulang
            </button>
          </div>
        ) : (
          offerings.map((offering) => {
            const placedCourse = semesterCourses.find(
              (c) =>
                c.id === offering.courseId || c.code === offering.courseCode,
            )
            const currentSectionId =
              selectedSections[offering.courseId] ||
              offering.sections[0]?.sectionId ||
              ""
            const hasConflict = conflictingCourseIds.has(offering.courseCode)

            return (
              <div
                key={offering.courseId}
                className={cn(
                  "p-3.5 rounded-xl border transition-all",
                  hasConflict
                    ? "bg-danger/4 border-danger/40 ring-1 ring-danger/20"
                    : "bg-background border-border/80 hover:border-gold/50",
                )}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-mono text-xs font-bold text-navy bg-navy/8 px-1.5 py-0.5 rounded">
                        {offering.courseCode}
                      </span>
                      <span className="text-[11px] font-mono text-muted">
                        {offering.credits} SKS
                      </span>
                      {placedCourse?.type && (
                        <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-surface border border-border text-navy">
                          {placedCourse.type}
                        </span>
                      )}
                    </div>
                    <h4 className="font-medium text-sm text-foreground break-words">
                      {offering.courseName}
                    </h4>
                  </div>

                  {hasConflict && (
                    <span className="flex-shrink-0 flex items-center gap-1 text-[11px] font-semibold text-danger bg-danger/10 px-2 py-0.5 rounded-md">
                      <AlertTriangle className="w-3 h-3" />
                      Bentrok
                    </span>
                  )}
                </div>

                {offering.sections.length === 0 ? (
                  <div className="p-3 rounded-lg border border-dashed border-border bg-surface">
                    <p className="text-xs font-medium text-navy">
                      Belum ada kelas untuk {offering.courseCode}
                    </p>
                    <p className="text-[11px] text-foreground mt-1">
                      Section untuk {periodLabel} belum diterbitkan atau kode
                      mata kuliah belum terdaftar di akademik. Periksa kembali
                      setelah jadwal KRS tersedia, atau hubungi akademik prodi.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                    {offering.sections.map((sec) => {
                      const isSelected = currentSectionId === sec.sectionId

                      return (
                        <button
                          key={sec.sectionId}
                          type="button"
                          disabled={!scheduleIsFinal}
                          onClick={() =>
                            onSelectSection(offering.courseId, sec.sectionId)
                          }
                          className={cn(
                            "min-h-11 p-2.5 rounded-lg border text-left transition-all cursor-pointer flex flex-col justify-between gap-1 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-border",
                            isSelected
                              ? "bg-navy text-white border-navy shadow-2xs font-medium"
                              : "bg-surface border-border hover:border-navy/30 text-foreground",
                          )}
                        >
                          <div className="flex items-center justify-between w-full">
                            <span
                              className={cn(
                                "font-bold text-xs",
                                isSelected ? "text-gold" : "text-navy",
                              )}
                            >
                              {sec.sectionCode}
                            </span>
                            {sec.capacity != null && (
                              <span
                                className={cn(
                                  "text-[10px] font-mono",
                                  isSelected ? "text-white/80" : "text-muted",
                                )}
                              >
                                Kuota {sec.capacity}
                              </span>
                            )}
                          </div>

                          {sec.schedules.length === 0 ? (
                            <p
                              className={cn(
                                "text-xs",
                                isSelected ? "text-white" : "text-foreground",
                              )}
                            >
                              Jadwal pertemuan belum ditetapkan.
                            </p>
                          ) : (
                            <div className="w-full space-y-1.5">
                              {sec.schedules.map((slot, index) => (
                                <div
                                  key={`${slot.dayOfWeek}-${slot.start}-${index}`}
                                  className="w-full"
                                >
                                  <div
                                    className={cn(
                                      "flex items-center gap-1 text-xs",
                                      isSelected
                                        ? "text-white"
                                        : "text-foreground",
                                    )}
                                  >
                                    <Clock
                                      className={cn(
                                        "w-3 h-3 flex-shrink-0",
                                        isSelected ? "text-gold" : "text-muted",
                                      )}
                                    />
                                    <span className="font-medium">
                                      {slot.day}, {formatTime(slot.start)}–
                                      {formatTime(slot.end)}
                                    </span>
                                  </div>
                                  <div
                                    className={cn(
                                      "flex items-center gap-1 text-[11px] pt-0.5",
                                      isSelected
                                        ? "text-white/80"
                                        : "text-muted",
                                    )}
                                  >
                                    <MapPin className="w-3 h-3 flex-shrink-0" />
                                    <span className="break-words">
                                      {slot.room}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      <div className="pt-3 border-t border-border flex items-center justify-between text-xs text-muted">
        <span>
          Terpilih: <strong className="text-navy">{selectedCount}</strong> dari{" "}
          {semesterCourses.length} matkul
        </span>
        <span className="font-mono text-[11px]">
          {conflicts.length === 0
            ? "Jadwal Valid"
            : `${conflicts.length} Konflik Perlu Dibenahi`}
        </span>
      </div>
    </div>
  )
}
