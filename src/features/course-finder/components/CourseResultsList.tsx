import { BookOpen, CheckCircle2, Clock, Edit3, Flame, Star } from "lucide-react"
import type { AuthUser } from "@/features/auth/authService"
import type {
  PollingPeriod,
  StudentVote,
} from "@/features/polling/pollingService"
import type { Course } from "@/shared/domain/models"
import CourseIdentityBadges from "@/shared/ui/course/CourseIdentityBadges"
import { cn } from "@/shared/utils"

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
          {filtered.map((course) => (
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
                  {course.type === "Pilihan" &&
                    (() => {
                      const votes = votesFor(course)
                      const minQ = pollingPeriod?.min_quorum ?? 0
                      const isElectiveOpen = votes >= minQ
                      return (
                        <span
                          className={cn(
                            "px-1.5 py-0.5 rounded text-[9px] font-bold",
                            isElectiveOpen
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                              : "bg-zinc-100 text-zinc-700 border border-zinc-200",
                          )}
                        >
                          {isElectiveOpen ? "Dibuka" : "Ditutup"}
                        </span>
                      )
                    })()}
                </div>
              </div>
              {course.type === "Pilihan" &&
                (() => {
                  const votes = votesFor(course)
                  const minQ = pollingPeriod?.min_quorum ?? 0
                  const isElectiveOpen = votes >= minQ
                  const rank = rankedCourseCodes[course.code || course.id]
                  return (
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
                          className={cn(
                            "font-medium",
                            isElectiveOpen ? "text-emerald-700" : "text-muted",
                          )}
                        >
                          {isElectiveOpen
                            ? "Tersedia Kelas Kuliah"
                            : "Ditutup Semester Ini"}
                        </span>
                        {currentUser?.role === "student" &&
                          (() => {
                            const vote = voteFor(course)
                            const targetSem = course.semester || 6
                            return (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  onOpenPriorityModal(course)
                                }}
                                className={cn(
                                  "min-h-11 min-w-11 px-2 rounded-md text-[11px] font-bold flex items-center gap-1 cursor-pointer transition-colors shadow-xs",
                                  vote
                                    ? "bg-gold text-navy hover:bg-gold/90"
                                    : "bg-navy text-white hover:bg-navy-light",
                                )}
                                title={
                                  vote
                                    ? "Perbarui prioritas voting Pra-KRS"
                                    : "Beri vote prioritas agar kelas dibuka di semester mendatang"
                                }
                              >
                                <Star
                                  className={cn(
                                    "w-3 h-3",
                                    vote ? "fill-navy text-navy" : "text-gold",
                                  )}
                                />
                                <span>
                                  {vote
                                    ? `★ Wishlist P${vote.priority}`
                                    : `☆ Vote Sem ${targetSem}`}
                                </span>
                              </button>
                            )
                          })()}
                      </div>
                    </div>
                  )
                })()}
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
          ))}
        </div>
      )}
    </div>
  )
}
