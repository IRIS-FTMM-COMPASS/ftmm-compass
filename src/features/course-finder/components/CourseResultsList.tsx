import {
  BookOpen,
  CheckCircle2,
  Clock,
  Edit3,
  Flame,
  Lock,
  Star,
} from "lucide-react"
import type { AuthUser } from "@/features/auth/authService"
import type {
  PollingPeriod,
  StudentVote,
} from "@/features/polling/pollingService"
import type { Course } from "@/shared/domain/models"
import CourseIdentityBadges from "@/shared/ui/course/CourseIdentityBadges"
import { cn } from "@/shared/utils"
import { isCourseLocked, type CourseLockStatus } from "@/shared/domain/course"

function getLockReason(
  reason: CourseLockStatus["reason"],
  pollingPeriod: PollingPeriod | null,
): string {
  if (reason === "pj") return "MK Terkunci: dinonaktifkan oleh PJ Prodi"
  if (reason === "parity") {
    const term = pollingPeriod?.target_semester_type ?? pollingPeriod?.term
    const termLabel = term === "genap" ? "genap" : "ganjil"
    return `MK Terkunci: paritas MK tidak sesuai dengan semester ${termLabel} pada periode polling`
  }
  return ""
}

interface CourseResultsListProps {
  filtered: Course[]
  catalogLoading: boolean
  onSelectCourse: (course: Course) => void
  currentUser: AuthUser | null
  onEditCourse: (course: Course) => void
  votesFor: (course: Course) => number
  pollingPeriod: PollingPeriod | null
  rankedCourseCodes: Record<string, number>
  voteFor: (course: Course) => StudentVote | undefined
  onOpenPriorityModal: (course: Course) => void
  addedCourseIds: Set<string>
}

export default function CourseResultsList({
  filtered,
  catalogLoading,
  onSelectCourse,
  currentUser,
  onEditCourse,
  votesFor,
  pollingPeriod,
  rankedCourseCodes,
  voteFor,
  onOpenPriorityModal,
  addedCourseIds,
}: CourseResultsListProps) {
  return (
    <div className="flex-1 overflow-y-auto">
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted">
          <BookOpen className="w-10 h-10 opacity-20 mb-3" />
          <p className="text-sm">
            {catalogLoading
              ? "Memuat katalog dari backend..."
              : "Tidak ada mata kuliah yang sesuai filter."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-4">
          {filtered.map((course) => {
            const lock = isCourseLocked(course, pollingPeriod)
            const lockReason = getLockReason(lock.reason, pollingPeriod)
            const votes = votesFor(course)
            const minQ = pollingPeriod?.min_quorum ?? 0
            const rank = rankedCourseCodes[course.code || course.id]
            const isElectiveOpen = !lock.locked && votes >= minQ
            return (
              <div
                key={course.id}
                onClick={() => onSelectCourse(course)}
                className="bg-surface rounded-xl border border-border p-4 cursor-pointer hover:border-gold hover:shadow-md transition-all flex flex-col gap-3 group"
              >
                <div className="flex justify-between items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <CourseIdentityBadges course={course} />
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-heading font-semibold text-base text-foreground mt-1.5 group-hover:text-gold transition-colors line-clamp-1">
                        {course.name}
                      </h3>
                      {currentUser?.role === "admin" && (
                        <button
                          type="button"
                          title="Edit Mata Kuliah"
                          onClick={(e) => {
                            e.stopPropagation()
                            onEditCourse(course)
                          }}
                          className="min-h-11 min-w-11 flex items-center justify-center rounded-md text-muted hover:text-navy hover:bg-background border border-border/60 transition-colors cursor-pointer flex-shrink-0"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider",
                        course.type === "Wajib"
                          ? "bg-navy/8 text-navy"
                          : "bg-gold/10 text-navy",
                      )}
                    >
                      {course.type}
                    </span>
                    {lock.locked ? (
                      <span
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-background border border-border text-muted"
                        title={lockReason}
                      >
                        <Lock
                          className="w-3 h-3 flex-shrink-0"
                          aria-hidden="true"
                        />
                        MK Terkunci
                      </span>
                    ) : (
                      course.type === "Pilihan" && (
                        <span
                          className={cn(
                            "px-1.5 py-0.5 rounded text-[9px] font-bold",
                            isElectiveOpen
                              ? "bg-teal/10 text-navy border border-teal/30"
                              : "bg-background text-muted border border-border",
                          )}
                        >
                          {isElectiveOpen ? "Dibuka" : "Ditutup"}
                        </span>
                      )
                    )}
                  </div>
                </div>
                {course.type === "Pilihan" && (
                  <div className="flex flex-col gap-2 p-2.5 rounded-lg bg-background border border-border/70 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 font-medium text-[11px] text-muted">
                        <Flame
                          className={cn(
                            "w-3.5 h-3.5 flex-shrink-0",
                            votes > 0 ? "text-orange" : "text-muted",
                          )}
                        />
                        <span>
                          <strong className="text-navy font-mono font-bold">
                            {votes}
                          </strong>{" "}
                          peminat
                          {pollingPeriod ? ` / Min. ${minQ}` : ""}
                        </span>
                      </div>
                      {rank && votes > 0 && (
                        <span className="text-[10px] font-bold text-orange bg-orange/10 px-1.5 py-0.5 rounded border border-orange/20">
                          #{rank} Paling Diminati
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between gap-2 pt-1.5 border-t border-border/40 text-[11px]">
                      <span
                        id={`lock-reason-${course.id}`}
                        className={cn(
                          "font-medium",
                          lock.locked || !isElectiveOpen
                            ? "text-muted"
                            : "text-emerald-700",
                        )}
                      >
                        {lock.locked ? (
                          <span className="inline-flex items-center gap-1">
                            <Lock
                              className="w-3 h-3 flex-shrink-0"
                              aria-hidden="true"
                            />
                            {lockReason}
                          </span>
                        ) : isElectiveOpen ? (
                          "Tersedia Kelas Kuliah"
                        ) : (
                          "Ditutup Semester Ini"
                        )}
                      </span>
                      {currentUser?.role === "student" &&
                        (() => {
                          const vote = voteFor(course)
                          const targetSem = course.semester || 6
                          return (
                            <button
                              type="button"
                              disabled={lock.locked}
                              aria-disabled={lock.locked}
                              aria-label={lock.locked ? lockReason : undefined}
                              aria-describedby={
                                lock.locked
                                  ? `lock-reason-${course.id}`
                                  : undefined
                              }
                              onClick={(e) => {
                                if (lock.locked) return
                                e.stopPropagation()
                                onOpenPriorityModal(course)
                              }}
                              className={cn(
                                "min-h-11 min-w-11 px-2 rounded-md text-[11px] font-bold flex items-center gap-1 transition-colors shadow-xs",
                                lock.locked
                                  ? "bg-background border border-border text-muted cursor-not-allowed"
                                  : vote
                                    ? "bg-gold text-navy hover:bg-gold/90 cursor-pointer"
                                    : "bg-navy text-white hover:bg-navy-light cursor-pointer",
                              )}
                              title={
                                lock.locked
                                  ? lockReason
                                  : vote
                                    ? "Perbarui prioritas peminatan MK Pilihan"
                                    : "Beri vote prioritas agar kelas dibuka di semester mendatang"
                              }
                            >
                              <Star
                                className={cn(
                                  "w-3 h-3",
                                  lock.locked
                                    ? "text-muted"
                                    : vote
                                      ? "fill-navy text-navy"
                                      : "text-gold",
                                )}
                              />
                              <span>
                                {vote
                                  ? `Peminatan MK Pilihan P${vote.priority}`
                                  : `Vote Sem ${targetSem}`}
                              </span>
                            </button>
                          )
                        })()}
                    </div>
                  </div>
                )}
                <p className="text-xs text-muted line-clamp-2 leading-relaxed">
                  {course.desc}
                </p>
                <div className="flex items-center justify-between pt-2 border-t border-border/50 text-xs text-muted mt-auto">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 font-medium">
                      <Clock className="w-3.5 h-3.5" /> {course.credits} SKS
                    </span>
                    <span>Sem {course.semester}</span>
                  </div>
                  <span
                    className={cn(
                      "text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ml-auto",
                      course.parity === "odd"
                        ? "bg-teal/10 text-navy"
                        : "bg-gold/10 text-navy",
                    )}
                  >
                    {course.parity === "odd" ? "Ganjil" : "Genap"}
                  </span>
                </div>
                {currentUser?.role === "student" &&
                  addedCourseIds.has(course.id) && (
                    <div className="flex items-center gap-1 text-[11px] font-medium text-teal mt-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Ditambahkan ke
                      Degree Planner
                    </div>
                  )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
