import { useState, useEffect, useMemo, useRef } from "react"
import { BookOpen, Calendar } from "lucide-react"
import { cn } from "@/shared/utils"
import {
  Course,
  type CourseOffering,
  type ClassSection,
  formatTime,
  getOfferingForCourse,
  ScheduleItem,
  TIMETABLE_DAYS,
} from "@/shared/domain/models"
import { SEMESTERS } from "@/shared/domain/academics"
import { courseReligion } from "@/shared/domain/course"
import TimetableGrid from "@/shared/timetable/TimetableGrid"
import DailyScheduleAccordion from "@/shared/timetable/DailyScheduleAccordion"
import {
  PlacedCourse,
  SemesterState,
  Tab,
  DegreePlannerProps,
  canDrop,
  courseKey,
} from "@/features/degree-planner/types"
import PlannerHeader from "@/features/degree-planner/components/PlannerHeader"
import SemesterSwitcher from "@/features/degree-planner/components/SemesterSwitcher"
import {
  SemesterColumn,
  ElectiveCourseBank,
} from "@/features/degree-planner/components/SemesterColumn"
import CoursePickerModal from "@/features/degree-planner/components/CoursePickerModal"
import CourseInspectModal from "@/features/degree-planner/components/CourseInspectModal"
import ClassSelectorPanel from "@/features/degree-planner/components/ClassSelectorPanel"
import {
  markConflicts,
  type ScheduleConflictDetail,
  type ScheduleValidationResult,
  type SectionAlternative,
  type TimetableConflict,
} from "@/shared/domain/timetable"
import { usePlanner } from "@/features/degree-planner/state/planner"
import { useSession } from "@/features/auth/session"
import { useAcademicPeriod } from "@/shared/academic-period/academic"
import { ApiError, apiErrorMessage } from "@/shared/api/client"
import {
  classSectionService,
  mapClassSection,
  type SectionSelectionInput,
} from "@/features/degree-planner/services/classSectionService"
import {
  planValidationService,
  type PlanValidationResult,
} from "@/features/degree-planner/services/planValidationService"
import { useReloadableFetch } from "@/features/degree-planner/state/useReloadableFetch"
import {
  timetableService,
  type TimetableSelectionInput,
} from "@/features/degree-planner/services/timetableService"
import { useSchedulingStatus } from "@/features/scheduling/hooks/useSchedulingStatus"

const EMPTY_SECTIONS: Record<string, ClassSection[]> = {}

function buildTimetableSelections(
  codes: string[],
  offerings: CourseOffering[],
  selectedSections: Record<string, string>,
): TimetableSelectionInput[] {
  return codes.flatMap((code) => {
    const offering = offerings.find((item) => item.courseCode === code)
    const sectionId = offering
      ? (selectedSections[offering.courseId] ??
        selectedSections[code] ??
        offering.sections[0]?.sectionId)
      : selectedSections[code]
    return sectionId ? [{ course_code: code, section_id: sectionId }] : []
  })
}

function selectionSignature(selections: TimetableSelectionInput[]): string {
  return selections
    .map((selection) => `${selection.course_code}:${selection.section_id}`)
    .sort()
    .join("|")
}

export type { PlacedCourse } from "@/features/degree-planner/types"

function toConflictDetail(conflict: TimetableConflict): ScheduleConflictDetail {
  return {
    courseACode: conflict.codeA,
    courseAName: conflict.courseA,
    sectionAId: "",
    sectionACode: conflict.sectionA,
    courseBCode: conflict.codeB,
    courseBName: conflict.courseB,
    sectionBId: "",
    sectionBCode: conflict.sectionB,
    day: conflict.day,
    start: formatTime(conflict.start),
    end: formatTime(conflict.end),
  }
}

export default function DegreePlanner({
  onNavigate,
  initialTab,
}: DegreePlannerProps) {
  const { period } = useAcademicPeriod()
  const planner = usePlanner()
  const { user } = useSession()
  const { isFinal } = useSchedulingStatus()
  const currentProgram = user?.student_profile?.study_program ?? null
  const {
    drafts,
    courses: catalog,
    activeDraftId,
    plan,
    isLoading,
    setPlan,
    switchDraft,
    createDraft,
    duplicateCurrentDraft,
    deleteDraft,
    resetCurrentDraft,
    isSaving,
    lastSaved,
    saveError,
    retrySave,
    pendingCourses,
    removePendingCourse,
    appliedSummary,
    resetPlan,
    setSchedule,
    completedBySemester,
    completedByKey,
    markPassed,
    unmarkPassed,
    isMutating: isMutatingRecord,
    error: recordError,
  } = planner
  const [activeTab, setActiveTab] = useState<Tab>(initialTab || "roadmap")
  const [activeRoadmapSem, setActiveRoadmapSem] = useState<number>(() =>
    Math.min(8, Math.max(1, user?.student_profile?.current_semester ?? 1)),
  )

  useEffect(() => {
    setActiveTab(initialTab || "roadmap")
  }, [initialTab])

  const [pickerSem, setPickerSem] = useState<number | null>(null)
  const [pickerSearch, setPickerSearch] = useState("")
  const [pickerType, setPickerType] = useState<"all" | "Pilihan" | "Wajib">(
    "all",
  )
  const [inspectCourse, setInspectCourse] = useState<{
    course: PlacedCourse
    sem: number
  } | null>(null)
  const [activeTimetableSem, setActiveTimetableSem] = useState<number>(() =>
    Math.min(8, Math.max(1, user?.student_profile?.current_semester ?? 1)),
  )
  const [timetableSemesterResolved, setTimetableSemesterResolved] =
    useState(false)
  const timetableSemesterResolvedRef = useRef(false)

  useEffect(() => {
    if (timetableSemesterResolvedRef.current || isLoading) return
    // The plan is only meaningful once drafts have been loaded from the
    // server. While the session is still resolving the drafts are empty, so
    // resolving here would be one-shot and skip the semester switch below.
    if (drafts.length === 0 && !activeDraftId) return
    timetableSemesterResolvedRef.current = true

    // A saved plan can place courses outside the student's current semester.
    const firstPopulated = SEMESTERS.find((sem) => (plan[sem]?.length ?? 0) > 0)
    if (firstPopulated === undefined) {
      // Every loaded draft is empty. Keep the current semester, but seed the
      // saved signature so hydration cannot send a destructive empty PUT that
      // would wipe a previously saved timetable.
      timetableSavedSignatureRef.current = effectiveSignature
    } else if ((plan[activeTimetableSem]?.length ?? 0) === 0) {
      // Switch before hydration/autosave are enabled so saved sections are
      // restored for the populated semester instead of an empty one.
      setActiveTimetableSem(firstPopulated)
    }
    setTimetableSemesterResolved(true)
  }, [isLoading, plan, activeTimetableSem, drafts.length, activeDraftId])

  const [selectedSections, setSelectedSections] =
    useState<Record<string, string>>({})
  const [planValidation, setPlanValidation] =
    useState<PlanValidationResult | null>(null)
  const [planValidationPending, setPlanValidationPending] = useState(false)
  const [planValidationError, setPlanValidationError] = useState<string | null>(
    null,
  )
  const planValidationController = useRef<AbortController | null>(null)
  const [timetableSaveStatus, setTimetableSaveStatus] =
    useState<"idle" | "saving" | "saved" | "error">("idle")
  const timetableHydratedRef = useRef(false)
  const [timetableHydrated, setTimetableHydrated] = useState(false)
  const timetableSavedSignatureRef = useRef<string | null>(null)
  const timetableTouchedRef = useRef(false)
  const timetableMountedRef = useRef(true)
  const activeReligion = useMemo(() => {
    const completed = Object.values(completedBySemester).flat()
    for (const courses of [...Object.values(plan), completed]) {
      for (const c of courses) {
        const rel = courseReligion(c)
        if (rel && rel !== "Umum") return rel
      }
    }
    return null
  }, [completedBySemester, plan])

  const placedMap = useMemo(() => {
    const map = new Map<string, number>()
    Object.entries(plan).forEach(([semStr, list]) => {
      list.forEach((c) => map.set(courseKey(c), Number(semStr)))
    })
    Object.entries(completedBySemester).forEach(([semStr, list]) => {
      list.forEach((c) => map.set(courseKey(c), Number(semStr)))
    })
    return map
  }, [completedBySemester, plan])

  const completedKeys = useMemo(
    () => new Set(completedByKey.keys()),
    [completedByKey],
  )

  const displayPlan = useMemo(() => {
    const merged: Record<number, PlacedCourse[]> = {}
    const semesters = new Set([
      ...Object.keys(plan),
      ...Object.keys(completedBySemester),
    ])
    for (const key of semesters) {
      const semester = Number(key)
      merged[semester] = [
        ...(completedBySemester[semester] ?? []),
        ...(plan[semester] ?? []),
      ]
    }
    return merged
  }, [completedBySemester, plan])

  useEffect(() => {
    if (completedKeys.size === 0) return
    const hasDuplicate = Object.values(plan).some((list) =>
      list.some((course) => completedKeys.has(courseKey(course))),
    )
    if (!hasDuplicate) return
    setPlan((prev) => {
      const next: Record<number, PlacedCourse[]> = {}
      for (const [semester, list] of Object.entries(prev)) {
        next[Number(semester)] = list.filter(
          (course) => !completedKeys.has(courseKey(course)),
        )
      }
      return next
    })
  }, [completedKeys, plan, setPlan])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPickerSem(null)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const handleAddCourseFromModal = (course: Course) => {
    if (pickerSem === null) return
    const key = courseKey(course)
    if (placedMap.has(key)) return
    const newCourse: PlacedCourse = {
      ...course,
      semester: pickerSem,
      status: "planned",
    }
    setPlan((prev) => ({
      ...prev,
      [pickerSem]: [...(prev[pickerSem] || []), newCourse],
    }))
    removePendingCourse(course.id)
  }

  const [dragging, setDragging] = useState<{
    course: PlacedCourse
    fromSem: number | "bank"
    fromIndex?: number
  } | null>(null)
  const [hoverSem, setHoverSem] = useState<number | null>(null)
  const [dropTarget, setDropTarget] = useState<{
    sem: number
    index: number
  } | null>(null)

  useEffect(() => {
    const wajibCourses = pendingCourses.filter((c) => c.type === "Wajib")
    if (wajibCourses.length === 0) return

    setPlan((prev) => {
      const next = { ...prev }
      wajibCourses.forEach((course) => {
        const sem = course.semester
        if (!next[sem]) next[sem] = []
        if (!next[sem].find((c) => courseKey(c) === courseKey(course))) {
          next[sem] = [...next[sem], { ...course, status: "planned" }]
        }
      })
      return next
    })
    wajibCourses.forEach((course) => removePendingCourse(course.id))
  }, [pendingCourses, removePendingCourse, setPlan])

  const semState = (sem: number): SemesterState => {
    if (!dragging) return "idle"
    const valid = canDrop(dragging.course, sem, dragging.fromSem)
    const hovering = hoverSem === sem
    if (!valid) return hovering ? "invalid-hover" : "invalid"
    return hovering ? "valid-hover" : "idle"
  }

  const handleDragStart = (
    e: React.DragEvent,
    course: PlacedCourse,
    from: number | "bank",
    fromIndex?: number,
  ) => {
    setDragging({ course, fromSem: from, fromIndex })
    e.dataTransfer.effectAllowed = "move"
    try {
      e.dataTransfer.setData("text/plain", course.id)
    } catch {}
  }

  const handleCardDragOver = (e: React.DragEvent, sem: number, idx: number) => {
    if (!dragging) return
    if (!canDrop(dragging.course, sem, dragging.fromSem)) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = "move"
    const rect = e.currentTarget.getBoundingClientRect()
    const insertAfter = e.clientY > rect.top + rect.height / 2
    setHoverSem(sem)
    setDropTarget({ sem, index: insertAfter ? idx + 1 : idx })
  }

  const handleCardDrop = (e: React.DragEvent, sem: number, idx: number) => {
    e.preventDefault()
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    const insertAfter = e.clientY > rect.top + rect.height / 2
    const targetIdx = insertAfter ? idx + 1 : idx
    handleDrop(e, sem, targetIdx)
  }

  const handleDragOver = (e: React.DragEvent, sem: number) => {
    if (!dragging) return
    if (canDrop(dragging.course, sem, dragging.fromSem)) {
      e.preventDefault()
      e.dataTransfer.dropEffect = "move"
    }
    setHoverSem(sem)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setHoverSem(null)
      setDropTarget(null)
    }
  }

  const handleDrop = (
    e: React.DragEvent,
    sem: number,
    explicitTargetIndex?: number,
  ) => {
    e.preventDefault()
    if (!dragging || !canDrop(dragging.course, sem, dragging.fromSem)) return

    const { course, fromSem, fromIndex } = dragging
    const targetIdx =
      explicitTargetIndex !== undefined
        ? explicitTargetIndex
        : dropTarget?.sem === sem
          ? dropTarget.index
          : plan[sem]?.length || 0

    if (fromSem === sem) {
      setPlan((prev) => {
        const currentList = [...(prev[sem] || [])]
        const fromIdx =
          fromIndex !== undefined
            ? fromIndex
            : currentList.findIndex((c) => c.id === course.id)
        if (fromIdx === -1) return prev
        const [removed] = currentList.splice(fromIdx, 1)
        let insertAt =
          explicitTargetIndex !== undefined
            ? explicitTargetIndex
            : dropTarget?.sem === sem
              ? dropTarget.index
              : currentList.length
        if (insertAt > fromIdx) {
          insertAt -= 1
        }
        insertAt = Math.max(0, Math.min(insertAt, currentList.length))
        currentList.splice(insertAt, 0, removed)
        return { ...prev, [sem]: currentList }
      })
    } else if (fromSem === "bank") {
      removePendingCourse(course.id)
      setPlan((prev) => {
        const currentList = [...(prev[sem] || [])]
        const insertAt = Math.max(0, Math.min(targetIdx, currentList.length))
        currentList.splice(insertAt, 0, {
          ...course,
          semester: sem,
          status: course.status || "planned",
        })
        return { ...prev, [sem]: currentList }
      })
    } else {
      setPlan((prev) => {
        const sourceList = (prev[fromSem] || []).filter(
          (c) => c.id !== course.id,
        )
        const targetList = [...(prev[sem] || [])]
        const insertAt = Math.max(0, Math.min(targetIdx, targetList.length))
        targetList.splice(insertAt, 0, {
          ...course,
          semester: sem,
          status: course.status || "planned",
        })
        return {
          ...prev,
          [fromSem]: sourceList,
          [sem]: targetList,
        }
      })
    }

    setDragging(null)
    setHoverSem(null)
    setDropTarget(null)
  }

  const handleDragEnd = () => {
    setDragging(null)
    setHoverSem(null)
    setDropTarget(null)
  }

  const deleteCourse = (courseId: string, sem: number) => {
    setPlan((prev) => ({
      ...prev,
      [sem]: (prev[sem] || []).filter((c) => c.id !== courseId),
    }))
  }

  const currentTimetableCourses = useMemo(
    () => plan[activeTimetableSem] || [],
    [plan, activeTimetableSem],
  )
  const timetableCodes = useMemo(
    () => [
      ...new Set(
        currentTimetableCourses.map((course) => course.code || course.id),
      ),
    ],
    [currentTimetableCourses],
  )
  const timetableCodeKey = timetableCodes.join("|")
  const sectionsState = useReloadableFetch<Record<string, ClassSection[]>>(
    (signal) => {
      if (timetableCodes.length === 0) return null
      return Promise.all(
        timetableCodes.map(async (code) => {
          try {
            const dtos = await classSectionService.list(code, signal)
            return [code, dtos.map(mapClassSection)] as const
          } catch (error) {
            if (signal.aborted) throw error
            if (error instanceof ApiError && error.status === 404) {
              return [code, []] as const
            }
            throw error
          }
        }),
      ).then((entries) => Object.fromEntries(entries))
    },
    [timetableCodeKey],
    "Jadwal kelas tidak dapat dimuat.",
    EMPTY_SECTIONS,
  )
  const sectionsByCourse = sectionsState.data ?? EMPTY_SECTIONS

  const offerings = useMemo(
    () =>
      currentTimetableCourses.map((course) =>
        getOfferingForCourse(
          course,
          sectionsByCourse[course.code || course.id] ?? [],
        ),
      ),
    [currentTimetableCourses, sectionsByCourse],
  )
  const effectiveSelections = useMemo(
    () => buildTimetableSelections(timetableCodes, offerings, selectedSections),
    [timetableCodes, offerings, selectedSections],
  )
  const effectiveSignature = useMemo(
    () => selectionSignature(effectiveSelections),
    [effectiveSelections],
  )

  useEffect(() => {
    timetableMountedRef.current = true
    return () => {
      timetableMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!timetableSemesterResolved || timetableHydratedRef.current) return
    // The initial empty fetch leaves stale section data; wait for the
    // resolved semester's sections before hydrating saved selections.
    if (
      sectionsState.status !== "ready" ||
      !timetableCodes.every((code) => sectionsByCourse[code] !== undefined)
    ) {
      return
    }

    // Nothing to hydrate from the API. Mark hydration complete so an empty
    // selection set can still be persisted to clear a stale timetable.
    if (
      timetableCodes.length === 0 ||
      !offerings.some((offering) => offering.sections.length > 0)
    ) {
      timetableHydratedRef.current = true
      setTimetableHydrated(true)
      return
    }

    timetableHydratedRef.current = true
    if (timetableTouchedRef.current) {
      setTimetableHydrated(true)
      return
    }

    timetableService
      .get()
      .then((response) => {
        if (!timetableMountedRef.current || timetableTouchedRef.current) {
          return
        }
        const savedByCode = new Map(
          response.selections
            .filter((item) => timetableCodes.includes(item.course_code))
            .map((item) => [item.course_code, item.section_id] as const),
        )
        if (savedByCode.size > 0) {
          const restoredEntries: Record<string, string> = {}
          offerings.forEach((offering) => {
            const sectionId = savedByCode.get(offering.courseCode)
            if (sectionId) restoredEntries[offering.courseId] = sectionId
          })
          timetableSavedSignatureRef.current = selectionSignature(
            buildTimetableSelections(timetableCodes, offerings, {
              ...selectedSections,
              ...restoredEntries,
            }),
          )
          setSelectedSections((prev) => {
            if (timetableTouchedRef.current) return prev
            return { ...prev, ...restoredEntries }
          })
        }
      })
      .catch(() => {})
      .finally(() => {
        if (timetableMountedRef.current) setTimetableHydrated(true)
      })
  }, [
    timetableSemesterResolved,
    sectionsState.status,
    timetableCodes,
    offerings,
    selectedSections,
    sectionsByCourse,
  ])

  useEffect(() => {
    if (!timetableSemesterResolved || !timetableHydrated) return
    if (effectiveSignature === timetableSavedSignatureRef.current) return

    const controller = new AbortController()
    setTimetableSaveStatus("saving")
    const timer = window.setTimeout(() => {
      timetableService
        .replace(effectiveSelections, controller.signal)
        .then(() => {
          if (controller.signal.aborted) return
          timetableSavedSignatureRef.current = effectiveSignature
          setTimetableSaveStatus("saved")
          window.dispatchEvent(new Event("timetable-updated"))
        })
        .catch(() => {
          if (!controller.signal.aborted) setTimetableSaveStatus("error")
        })
    }, 500)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [
    timetableSemesterResolved,
    timetableHydrated,
    effectiveSignature,
    effectiveSelections,
  ])

  const validationState = useReloadableFetch<ScheduleValidationResult>(
    (signal) => {
      if (sectionsState.status !== "ready") return null
      const selections: SectionSelectionInput[] = offerings.flatMap(
        (offering) => {
          const sectionId =
            selectedSections[offering.courseId] ??
            offering.sections[0]?.sectionId
          return sectionId
            ? [{ courseCode: offering.courseCode, sectionId }]
            : []
        },
      )
      if (selections.length === 0) return null
      return classSectionService.validate(selections, signal)
    },
    [offerings, selectedSections, sectionsState.status],
    "Validasi bentrok tidak dapat dimuat.",
  )
  const validation = validationState.data

  const { dynamicSchedule, conflicts } = useMemo(() => {
    const COLOR_PALETTE = [
      "bg-teal/20 text-navy border-teal/50",
      "bg-gold/20 text-navy border-gold/50",
      "bg-navy/10 text-navy border-navy/30",
      "bg-purple-100 text-purple-900 border-purple-300",
      "bg-blue-100 text-blue-900 border-blue-300",
      "bg-emerald-100 text-emerald-900 border-emerald-300",
    ]

    const items: ScheduleItem[] = []
    offerings.forEach((offering, index) => {
      const section =
        offering.sections.find(
          (candidate) =>
            candidate.sectionId === selectedSections[offering.courseId],
        ) ?? offering.sections[0]
      if (!section) return

      section.schedules.forEach((slot) => {
        items.push({
          id: `${offering.courseId}-${section.sectionId}-${slot.dayOfWeek}-${slot.start}`,
          course: offering.courseName,
          code: offering.courseCode,
          sectionCode: section.sectionCode,
          day: slot.day,
          start: slot.start,
          duration: slot.end - slot.start,
          color: COLOR_PALETTE[index % COLOR_PALETTE.length],
          room: slot.room,
          lecturer: section.lecturer,
        })
      })
    })

    const localConflicts = markConflicts(items)
    const displayedConflicts: ScheduleConflictDetail[] = validation
      ? validation.conflicts
      : localConflicts.map(toConflictDetail)
    if (validation) {
      const conflictingSections = new Set<string>()
      validation.conflicts.forEach((conflict) => {
        conflictingSections.add(
          `${conflict.courseACode}:${conflict.sectionACode}`,
        )
        conflictingSections.add(
          `${conflict.courseBCode}:${conflict.sectionBCode}`,
        )
      })
      items.forEach((item) => {
        item.conflict = conflictingSections.has(
          `${item.code}:${item.sectionCode}`,
        )
      })
    }
    return { dynamicSchedule: items, conflicts: displayedConflicts }
  }, [offerings, selectedSections, validation])

  // Jadwal semester aktif menjadi sumber untuk widget dashboard.
  useEffect(() => {
    setSchedule(dynamicSchedule)
  }, [dynamicSchedule, setSchedule])

  const handleSelectSection = (courseId: string, sectionId: string) => {
    timetableTouchedRef.current = true
    setSelectedSections((prev) => ({
      ...prev,
      [courseId]: sectionId,
    }))
  }

  const handleApplyAlternative = (alternative: SectionAlternative) => {
    const offering = offerings.find(
      (candidate) => candidate.courseCode === alternative.courseCode,
    )
    if (!offering) return

    timetableTouchedRef.current = true
    sectionsState.update((prev) => {
      const current = prev?.[alternative.courseCode] ?? []
      if (current.some((s) => s.sectionId === alternative.section.sectionId)) {
        return prev
      }
      return {
        ...(prev ?? EMPTY_SECTIONS),
        [alternative.courseCode]: [...current, alternative.section],
      }
    })
    setSelectedSections((prev) => ({
      ...prev,
      [offering.courseId]: alternative.section.sectionId,
    }))
  }

  const handleAutoResolveConflicts = () => {
    const applied = new Set<string>()
    validation?.alternatives.forEach((alternative) => {
      if (applied.has(alternative.courseCode)) return
      applied.add(alternative.courseCode)
      handleApplyAlternative(alternative)
    })
  }

  useEffect(() => () => planValidationController.current?.abort(), [])

  const handleValidatePlan = async () => {
    planValidationController.current?.abort()
    const controller = new AbortController()
    planValidationController.current = controller
    setPlanValidationPending(true)
    setPlanValidation(null)
    setPlanValidationError(null)
    try {
      const result = await planValidationService.validate(
        {
          program_studi:
            user?.student_profile?.study_program ?? "Teknologi Sains Data",
          semester_saat_ini: user?.student_profile?.current_semester ?? 1,
          riwayat_matkul_lulus: [...completedKeys],
          maks_sks_per_semester: 24,
          plan,
        },
        controller.signal,
      )
      if (!controller.signal.aborted) setPlanValidation(result)
    } catch (error) {
      if (controller.signal.aborted) return
      setPlanValidationError(
        apiErrorMessage(error, "Validasi rencana gagal dijalankan."),
      )
    } finally {
      if (!controller.signal.aborted) setPlanValidationPending(false)
    }
  }

  const renderSemesterColumn = (sem: number) => (
    <SemesterColumn
      key={sem}
      sem={sem}
      courses={plan[sem] || []}
      completedCourses={completedBySemester[sem] || []}
      state={semState(sem)}
      dragging={dragging}
      dropTarget={dropTarget}
      onDragOverColumn={handleDragOver}
      onDropColumn={handleDrop}
      onDragLeaveColumn={handleDragLeave}
      onCardDragStart={handleDragStart}
      onCardDragOver={handleCardDragOver}
      onCardDrop={handleCardDrop}
      onDragEnd={handleDragEnd}
      onDeleteCourse={deleteCourse}
      onOpenManualPicker={(s) => {
        setPickerSem(s)
        setPickerSearch("")
      }}
      onSelectCourse={(c) => setInspectCourse({ course: c, sem })}
    />
  )

  return (
    <div className="h-full flex flex-col animate-in fade-in duration-500">
      <div className="flex gap-1 mb-4 bg-background p-1 rounded-xl border border-border w-fit flex-shrink-0">
        {([
          { key: "roadmap", label: "Roadmap Studi", icon: BookOpen },
          { key: "timetable", label: "Jadwal Aktif", icon: Calendar },
        ] as const).map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "flex items-center gap-2 px-4 min-h-11 rounded-lg text-sm font-medium transition-all cursor-pointer",
                activeTab === tab.key
                  ? "bg-navy text-white shadow-sm"
                  : "text-muted hover:text-navy",
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {activeTab === "roadmap" && (
        <>
          <PlannerHeader
            appliedSummary={appliedSummary}
            onResetPlan={resetPlan}
            dragging={dragging}
            currentUser={user}
            drafts={drafts}
            activeDraftId={activeDraftId}
            onSwitchDraft={switchDraft}
            onCreateDraft={(name) => void createDraft(name)}
            onDuplicateDraft={duplicateCurrentDraft}
            onDeleteDraft={(draftId) => void deleteDraft(draftId)}
            onResetDraft={resetCurrentDraft}
            isSaving={isSaving}
            lastSaved={lastSaved}
            saveError={saveError}
            onRetrySave={retrySave}
          />

          {recordError && (
            <div className="mb-3 rounded-xl border border-orange/40 bg-orange/10 px-3.5 py-2.5 text-xs font-medium text-orange">
              {recordError}
            </div>
          )}

          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={() => void handleValidatePlan()}
              disabled={planValidationPending}
              className="min-h-11 px-3 rounded-lg bg-navy text-white text-xs font-semibold cursor-pointer hover:bg-navy-light focus-visible:outline-2 focus-visible:outline-navy focus-visible:outline-offset-2 disabled:opacity-60"
            >
              {planValidationPending
                ? "Memvalidasi rencana..."
                : "Validasi Rencana Studi"}
            </button>
            <div aria-live="polite" className="text-xs text-navy">
              {planValidation && (
                <p className="font-semibold">
                  Hasil validasi gateway:{" "}
                  {planValidation.isValid
                    ? `rencana valid, ${planValidation.totalCredits} SKS terencana`
                    : "rencana belum valid"}
                </p>
              )}
              {planValidation?.errors.map((message, index) => (
                <p key={`${message}-${index}`} className="mt-0.5 text-danger">
                  {message}
                </p>
              ))}
              {planValidation?.warnings.map((message, index) => (
                <p
                  key={`${message}-${index}`}
                  className="mt-0.5 text-foreground"
                >
                  {message}
                </p>
              ))}
              {planValidationError && (
                <p role="alert" className="mt-0.5 font-semibold text-danger">
                  {planValidationError}
                </p>
              )}
            </div>
          </div>

          <SemesterSwitcher
            id="roadmap-semester"
            value={activeRoadmapSem}
            counts={Object.fromEntries(
              SEMESTERS.map((sem) => [sem, (plan[sem] || []).length]),
            )}
            onChange={setActiveRoadmapSem}
          />

          <div className="hidden md:block flex-1 overflow-x-auto pb-1 min-h-0">
            <div className="flex gap-4 min-w-max h-full">
              {SEMESTERS.map((sem) => renderSemesterColumn(sem))}
            </div>
          </div>

          <div className="md:hidden flex-1 min-h-0 overflow-y-auto pb-2">
            {renderSemesterColumn(activeRoadmapSem)}
          </div>

          <ElectiveCourseBank
            pendingCourses={pendingCourses}
            onDragStartBank={(e, course) => handleDragStart(e, course, "bank")}
            onDragEnd={handleDragEnd}
            onSelectCourse={(c) =>
              setInspectCourse({ course: c, sem: c.semester || 5 })
            }
          />

          <CoursePickerModal
            pickerSem={pickerSem}
            pickerSearch={pickerSearch}
            setPickerSearch={setPickerSearch}
            currentProgram={currentProgram}
            pickerType={pickerType}
            setPickerType={setPickerType}
            catalog={catalog}
            placedMap={placedMap}
            completedKeys={completedKeys}
            onClose={() => setPickerSem(null)}
            onAddCourse={handleAddCourseFromModal}
            currentSemesterCourses={
              pickerSem !== null ? plan[pickerSem] || [] : []
            }
            activeReligion={activeReligion}
          />

          <CourseInspectModal
            course={inspectCourse ? inspectCourse.course : null}
            currentSem={inspectCourse ? inspectCourse.sem : 1}
            allPlan={displayPlan}
            onClose={() => setInspectCourse(null)}
            onDeleteCourse={deleteCourse}
            onMarkPassed={async (course, grade) => {
              const ok = await markPassed(course.code || course.id, grade)
              if (ok) setInspectCourse(null)
              return ok
            }}
            onUnmarkPassed={async (recordId) => {
              const ok = await unmarkPassed(recordId)
              if (ok) setInspectCourse(null)
              return ok
            }}
            isMutatingRecord={isMutatingRecord}
            completedGrade={
              inspectCourse
                ? (completedByKey.get(courseKey(inspectCourse.course))
                    ?.final_grade ?? null)
                : null
            }
            onOpenInCourseFinder={(c) => {
              onNavigate?.("course-finder", { course: c })
            }}
          />
        </>
      )}

      {activeTab === "timetable" && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="mb-4 flex flex-col md:flex-row md:flex-wrap md:justify-between md:items-center gap-3 flex-shrink-0">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-heading font-bold text-lg text-navy">
                  Jadwal Kuliah Aktif
                </h3>
                <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded-md bg-gold/15 text-navy border border-gold/30">
                  {period?.label ?? "—"}
                </span>
              </div>
              <p className="text-xs text-muted mt-0.5">
                Konfigurasikan kelas perkuliahan mahasiswa untuk melihat jadwal
                mingguan dan menyelesaikan bentrok waktu.
              </p>
              {timetableSaveStatus !== "idle" && (
                <p
                  role="status"
                  aria-live="polite"
                  className={cn(
                    "mt-1 text-xs font-medium",
                    timetableSaveStatus === "saving" && "text-muted",
                    timetableSaveStatus === "saved" && "text-navy",
                    timetableSaveStatus === "error" && "text-orange",
                  )}
                >
                  {timetableSaveStatus === "saving"
                    ? "Menyimpan jadwal…"
                    : timetableSaveStatus === "saved"
                      ? "Jadwal tersimpan"
                      : "Gagal menyimpan jadwal"}
                </p>
              )}
            </div>
            <SemesterSwitcher
              id="timetable-semester"
              value={activeTimetableSem}
              counts={Object.fromEntries(
                SEMESTERS.map((sem) => [sem, (plan[sem] || []).length]),
              )}
              onChange={setActiveTimetableSem}
            />

            <div className="hidden md:flex items-center gap-1.5 bg-background p-1 rounded-xl border border-border">
              <span className="text-xs text-muted font-medium px-2">
                Tampilkan Semester:
              </span>
              {SEMESTERS.map((sem) => {
                const count = (plan[sem] || []).length
                const isActive = activeTimetableSem === sem
                return (
                  <button
                    key={sem}
                    type="button"
                    onClick={() => setActiveTimetableSem(sem)}
                    className={cn(
                      "min-h-11 min-w-11 px-2 rounded-lg text-xs font-semibold transition-all cursor-pointer flex items-center gap-1",
                      isActive
                        ? "bg-navy text-white shadow-2xs"
                        : "text-muted hover:text-navy hover:bg-navy/5",
                    )}
                  >
                    <span>Sem {sem}</span>
                    {count > 0 && (
                      <span
                        className={cn(
                          "text-[9px] font-mono px-1 rounded-full",
                          isActive
                            ? "bg-white/20 text-white"
                            : "bg-surface text-muted border border-border",
                        )}
                      >
                        {count}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          <DailyScheduleAccordion
            schedule={dynamicSchedule}
            days={TIMETABLE_DAYS}
          />

          <div className="hidden md:flex flex-1 flex-col lg:grid lg:grid-cols-12 gap-4 min-h-0 overflow-y-auto lg:overflow-hidden pb-1 print:flex">
            <div className="lg:col-span-4 min-h-[380px] lg:h-full min-h-0 flex flex-col">
              <ClassSelectorPanel
                activeSemester={activeTimetableSem}
                scheduleIsFinal={isFinal}
                semesterCourses={currentTimetableCourses}
                offerings={offerings}
                selectedSections={selectedSections}
                onSelectSection={handleSelectSection}
                conflicts={conflicts}
                onAutoResolveConflicts={handleAutoResolveConflicts}
                periodLabel={period?.label ?? "periode akademik aktif"}
                sectionsState={sectionsState}
                validationState={validationState}
                onApplyAlternative={handleApplyAlternative}
              />
            </div>

            <div className="lg:col-span-8 flex flex-col min-h-0 h-full">
              <TimetableGrid
                schedule={dynamicSchedule}
                days={TIMETABLE_DAYS}
                semester={activeTimetableSem}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
