import { useCallback, useEffect, useReducer, useRef, useState } from "react"
import { ApiError, apiErrorMessage } from "@/shared/api/client"
import type { Course } from "@/shared/domain/models"
import { normalizeCourse } from "@/shared/domain/course"
import type { DegreePlanDraft, PlanCourse } from "@/shared/domain/plan"
import {
  degreePlanService,
  type DegreePlanDto,
  type DegreePlanItemDto,
  type DegreePlanItemInput,
  type PlannerCatalogItemDto,
} from "@/features/degree-planner/services/degreePlanService"
import { useSession } from "@/features/auth/session"
import {
  initialSaveState,
  plansDiffer,
  saveReducer,
  type PlanEntryRef,
} from "@/features/degree-planner/state/saveState"

const LEGACY_KEY = "ftmm_compass_degree_drafts_v2"

const DEFAULT_NAME = "Draft 1"
const SAVE_DELAY_MS = 500

interface LegacyCourse {
  code?: string
  semester?: number
}

interface LegacyDraft {
  name?: string
  plan?: Record<string, LegacyCourse[]>
}

interface LegacyState {
  activeDraftId?: string
  drafts?: LegacyDraft[]
}

function planFromDto(items: DegreePlanItemDto[]): Record<number, PlanCourse[]> {
  const plan: Record<number, PlanCourse[]> = {}
  const ordered = [...items].sort(
    (a, b) => a.semester - b.semester || a.code.localeCompare(b.code),
  )
  for (const item of ordered) {
    const course: PlanCourse = {
      id: item.id,
      code: item.code,
      name: item.name,
      credits: item.credits,
      semester: item.semester,
      type: item.type,
      parity: item.parity,
      desc: item.desc,
      status: "planned",
    }
    plan[item.semester] = [...(plan[item.semester] ?? []), course]
  }
  return plan
}

function planEntries(plan: Record<number, PlanCourse[]>): PlanEntryRef[] {
  return Object.entries(plan).flatMap(([semester, courses]) =>
    courses
      .filter((course) => Boolean(course.code))
      .map((course) => ({ code: course.code, semester: Number(semester) })),
  )
}

function dtoEntries(dto: DegreePlanDto): PlanEntryRef[] {
  return dto.items.map((item) => ({
    code: item.code,
    semester: item.semester,
  }))
}

function itemsFromPlan(
  plan: Record<number, PlanCourse[]>,
): DegreePlanItemInput[] {
  const items: DegreePlanItemInput[] = []
  for (const [semester, courses] of Object.entries(plan)) {
    for (const course of courses) {
      if (!course.code) continue
      items.push({
        course_code: course.code,
        planned_semester: Number(semester),
      })
    }
  }
  return items
}

function draftFromDto(dto: DegreePlanDto): DegreePlanDraft {
  return {
    id: dto.id,
    name: dto.name,
    status: dto.status,
    plan: planFromDto(dto.items),
    updatedAt: dto.updated_at,
  }
}

export interface PlanConflict {
  title: string
  message: string
  confirmLabel: string
}

export interface DegreeDraftsReturn {
  drafts: DegreePlanDraft[]
  courses: Course[]
  activeDraftId: string
  activeDraft: DegreePlanDraft | undefined
  plan: Record<number, PlanCourse[]>
  isLoading: boolean
  isSaving: boolean
  lastSaved: Date | null
  saveError: string | null
  planConflict: PlanConflict | null
  confirmPlanConflict: () => Promise<void>
  cancelPlanConflict: () => void
  setPlan: (
    updater: Record<number, PlanCourse[]> | ((
      prev: Record<number, PlanCourse[]>,
    ) => Record<number, PlanCourse[]>),
  ) => void
  switchDraft: (draftId: string) => Promise<void>
  createDraft: (name: string) => Promise<void>
  duplicateCurrentDraft: () => Promise<void>
  resetCurrentDraft: () => Promise<void>
  deleteDraft: (draftId: string) => Promise<boolean>
  retrySave: () => Promise<void>
}

export function useDegreeDrafts(): DegreeDraftsReturn {
  const { isLoggedIn } = useSession()
  const [drafts, setDrafts] = useState<DegreePlanDraft[]>([])
  const [activeDraftId, setActiveDraftId] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [save, dispatchSave] = useReducer(saveReducer, initialSaveState)
  const [planConflict, setPlanConflict] = useState<PlanConflict | null>(null)
  const [courses, setCourses] = useState<Course[]>([])

  const draftsRef = useRef(drafts)
  draftsRef.current = drafts
  const activeIdRef = useRef(activeDraftId)
  activeIdRef.current = activeDraftId
  const planRef = useRef<Record<number, PlanCourse[]>>({})
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const flushRef = useRef<() => Promise<void>>(async () => {})
  const pendingRef = useRef(false)
  const revisionRef = useRef(0)
  const loadedRef = useRef(false)
  const conflictActionRef = useRef<(() => Promise<void>) | null>(null)
  const conflictPendingRef = useRef(false)

  const activeDraft = drafts.find((draft) => draft.id === activeDraftId)
  const plan = activeDraft?.plan ?? {}

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const scheduleFlush = useCallback(
    (delay: number) => {
      clearTimer()
      timerRef.current = setTimeout(() => {
        timerRef.current = null
        void flushRef.current()
      }, delay)
    },
    [clearTimer],
  )

  const persist = useCallback(
    async (
      planId: string,
      nextPlan: Record<number, PlanCourse[]>,
      revision: number,
    ) => {
      if (!planId) return
      dispatchSave({ type: "save-start" })
      try {
        const dto = await degreePlanService.replaceItems(
          planId,
          itemsFromPlan(nextPlan),
        )
        setDrafts((prev) =>
          prev.map((draft) =>
            draft.id === dto.id && revision === revisionRef.current
              ? draftFromDto(dto)
              : draft.id === dto.id
                ? { ...draft, updatedAt: dto.updated_at }
                : draft,
          ),
        )
        dispatchSave({ type: "save-success", revision, at: new Date() })
        if (revision < revisionRef.current) {
          pendingRef.current = true
          scheduleFlush(0)
        }
      } catch (error) {
        dispatchSave({
          type: "save-failure",
          message: `Gagal menyimpan rencana: ${apiErrorMessage(error, "permintaan ke server gagal")}`,
        })
      }
    },
    [scheduleFlush],
  )

  const flush = useCallback(async () => {
    clearTimer()
    if (!pendingRef.current) return
    pendingRef.current = false
    const draftId = activeIdRef.current
    if (!draftId) return
    await persist(draftId, planRef.current, revisionRef.current)
  }, [clearTimer, persist])
  flushRef.current = flush

  const replaceDraft = useCallback((dto: DegreePlanDto) => {
    const next = draftFromDto(dto)
    if (dto.id === activeIdRef.current) planRef.current = next.plan
    setDrafts((prev) =>
      prev.map((draft) => (draft.id === next.id ? next : draft)),
    )
  }, [])

  const requestCopy = useCallback(
    async (planId: string, localPlan: Record<number, PlanCourse[]>) => {
      const dto = await degreePlanService.get(planId)
      return {
        dto,
        differs: plansDiffer(planEntries(localPlan), dtoEntries(dto)),
      }
    },
    [],
  )

  const openConflict = useCallback(
    (conflict: PlanConflict, action: () => Promise<void>, resume: boolean) => {
      conflictActionRef.current = action
      conflictPendingRef.current = resume
      setPlanConflict(conflict)
    },
    [],
  )

  const activate = useCallback(
    async (draftId: string, nextPlan: Record<number, PlanCourse[]>) => {
      if (draftId === activeIdRef.current) return
      planRef.current = nextPlan
      setActiveDraftId(draftId)
      try {
        const dto = await degreePlanService.update(draftId, {
          status: "active",
        })
        setDrafts((prev) =>
          prev.map((draft) =>
            draft.id === dto.id
              ? { ...draft, status: dto.status }
              : draft.status === "active"
                ? { ...draft, status: "draft" }
                : draft,
          ),
        )
        dispatchSave({ type: "clear-error" })
      } catch (error) {
        dispatchSave({
          type: "save-failure",
          message: apiErrorMessage(
            error,
            "Gagal mengaktifkan skenario rencana",
          ),
        })
      }
    },
    [],
  )

  const createWithName = useCallback(
    async (name: string, items: DegreePlanItemInput[]) => {
      let attempt = 1
      let candidate = name
      while (true) {
        try {
          return await degreePlanService.create({
            name: candidate,
            items,
          })
        } catch (error) {
          const conflict = error instanceof ApiError && error.status === 409
          if (!conflict || attempt >= 4) throw error
          attempt += 1
          candidate = `${name} (${attempt})`
        }
      }
    },
    [],
  )

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      await migrateLegacy(createWithName)
      const [catalogItems, response] = await Promise.all([
        degreePlanService.catalog(),
        degreePlanService.list(),
      ])
      setCourses(catalogItems.map(toCourse))
      if (response.data.length === 0) {
        const created = await createWithName(DEFAULT_NAME, [])
        await degreePlanService.update(created.id, { status: "active" })
        response.data = (await degreePlanService.list()).data
      }
      const nextDrafts = response.data.map(draftFromDto)
      const active =
        nextDrafts.find((draft) => draft.status === "active") ?? nextDrafts[0]
      clearTimer()
      pendingRef.current = false
      planRef.current = active?.plan ?? {}
      setDrafts(nextDrafts)
      setActiveDraftId(active?.id ?? "")
      setPlanConflict(null)
      conflictActionRef.current = null
      conflictPendingRef.current = false
      dispatchSave({
        type: "loaded",
        revision: revisionRef.current,
        at: new Date(),
      })
    } catch (error) {
      dispatchSave({
        type: "save-failure",
        message: apiErrorMessage(
          error,
          "Gagal memuat rencana studi dari server",
        ),
      })
    } finally {
      setIsLoading(false)
    }
  }, [clearTimer, createWithName])

  useEffect(() => {
    if (!isLoggedIn) {
      loadedRef.current = false
      clearTimer()
      pendingRef.current = false
      revisionRef.current = 0
      planRef.current = {}
      conflictActionRef.current = null
      conflictPendingRef.current = false
      setPlanConflict(null)
      setDrafts([])
      setCourses([])
      setActiveDraftId("")
      dispatchSave({ type: "cleared" })
      setIsLoading(false)
      return
    }
    if (loadedRef.current) return
    loadedRef.current = true
    void load()
  }, [clearTimer, isLoggedIn, load])

  useEffect(() => clearTimer, [clearTimer])

  const setPlan = useCallback(
    (
      updater: Record<number, PlanCourse[]> | ((
        prev: Record<number, PlanCourse[]>,
      ) => Record<number, PlanCourse[]>),
    ) => {
      const draftId = activeIdRef.current
      if (!draftId) return
      const revision = ++revisionRef.current
      const nextPlan =
        typeof updater === "function" ? updater(planRef.current) : updater
      planRef.current = nextPlan
      pendingRef.current = true
      dispatchSave({ type: "edit", revision })
      setDrafts((prev) =>
        prev.map((draft) =>
          draft.id === draftId ? { ...draft, plan: nextPlan } : draft,
        ),
      )
      scheduleFlush(SAVE_DELAY_MS)
    },
    [scheduleFlush],
  )

  const switchDraft = useCallback(
    async (draftId: string) => {
      if (draftId === activeIdRef.current) return
      const target = draftsRef.current.find((draft) => draft.id === draftId)
      await flush()
      await activate(draftId, target?.plan ?? {})
    },
    [activate, flush],
  )

  const createDraft = useCallback(
    async (name: string) => {
      await flush()
      try {
        const created = await createWithName(name, [])
        const next = draftFromDto(created)
        setDrafts((prev) => [...prev, next])
        await activate(created.id, next.plan)
      } catch (error) {
        dispatchSave({
          type: "save-failure",
          message: apiErrorMessage(
            error,
            "Gagal membuat skenario rencana baru",
          ),
        })
      }
    },
    [activate, createWithName, flush],
  )

  const duplicateCurrentDraft = useCallback(async () => {
    await flush()
    const source = draftsRef.current.find(
      (draft) => draft.id === activeIdRef.current,
    )
    if (!source) return
    try {
      const created = await createWithName(
        `${source.name} (Salinan)`,
        itemsFromPlan(source.plan),
      )
      const next = draftFromDto(created)
      setDrafts((prev) => [...prev, next])
      await activate(created.id, next.plan)
    } catch (error) {
      dispatchSave({
        type: "save-failure",
        message: apiErrorMessage(error, "Gagal menyalin skenario rencana"),
      })
    }
  }, [activate, createWithName, flush])

  const resetCurrentDraft = useCallback(async () => {
    clearTimer()
    const hadPending = pendingRef.current
    pendingRef.current = false
    const draftId = activeIdRef.current
    if (!draftId) return
    const localPlan = planRef.current
    try {
      const { dto, differs } = await requestCopy(draftId, localPlan)
      const apply = async () => {
        replaceDraft(dto)
        dispatchSave({
          type: "discard",
          revision: revisionRef.current,
          at: new Date(),
        })
      }
      if (differs) {
        openConflict(
          {
            title: "Versi server berbeda",
            message:
              "Perubahan lokal pada skenario ini berbeda dengan salinan di server. Muat salinan server dan buang perubahan lokal?",
            confirmLabel: "Muat versi server",
          },
          apply,
          hadPending,
        )
        return
      }
      await apply()
    } catch (error) {
      if (hadPending) {
        pendingRef.current = true
        scheduleFlush(SAVE_DELAY_MS)
      }
      dispatchSave({
        type: "save-failure",
        message: apiErrorMessage(
          error,
          "Gagal memuat ulang skenario dari server",
        ),
      })
    }
  }, [clearTimer, openConflict, replaceDraft, requestCopy, scheduleFlush])

  const deleteDraft = useCallback(
    async (draftId: string): Promise<boolean> => {
      if (draftsRef.current.length <= 1) return false
      await flush()
      try {
        await degreePlanService.remove(draftId)
      } catch (error) {
        dispatchSave({
          type: "save-failure",
          message: apiErrorMessage(error, "Gagal menghapus skenario rencana"),
        })
        return false
      }
      const remaining = draftsRef.current.filter(
        (draft) => draft.id !== draftId,
      )
      setDrafts(remaining)
      if (draftId === activeIdRef.current) {
        await activate(remaining[0].id, remaining[0].plan)
      }
      return true
    },
    [activate, flush],
  )

  const retrySave = useCallback(async () => {
    const draftId = activeIdRef.current
    if (!draftId) return
    const snapshot = planRef.current
    const revision = revisionRef.current
    try {
      const { differs } = await requestCopy(draftId, snapshot)
      const send = async () => {
        dispatchSave({ type: "retry" })
        await persist(draftId, snapshot, revision)
      }
      if (differs) {
        openConflict(
          {
            title: "Rencana di server berubah",
            message:
              "Salinan di server berbeda dengan draf lokal. Timpa salinan server dengan draf ini?",
            confirmLabel: "Timpa versi server",
          },
          send,
          false,
        )
        return
      }
      await send()
    } catch (error) {
      dispatchSave({
        type: "save-failure",
        message: `Gagal memeriksa salinan server: ${apiErrorMessage(error, "permintaan ke server gagal")}`,
      })
    }
  }, [openConflict, persist, requestCopy])

  const confirmPlanConflict = useCallback(async () => {
    const action = conflictActionRef.current
    conflictActionRef.current = null
    conflictPendingRef.current = false
    setPlanConflict(null)
    await action?.()
  }, [])

  const cancelPlanConflict = useCallback(() => {
    conflictActionRef.current = null
    const hadPending = conflictPendingRef.current
    conflictPendingRef.current = false
    setPlanConflict(null)
    if (hadPending) {
      pendingRef.current = true
      scheduleFlush(SAVE_DELAY_MS)
    }
  }, [scheduleFlush])

  return {
    drafts,
    courses,
    activeDraftId,
    activeDraft,
    plan,
    isLoading,
    isSaving: save.status === "saving",
    lastSaved: save.lastSaved,
    saveError: save.error,
    planConflict,
    confirmPlanConflict,
    cancelPlanConflict,
    setPlan,
    switchDraft,
    createDraft,
    duplicateCurrentDraft,
    resetCurrentDraft,
    deleteDraft,
    retrySave,
  }
}

async function migrateLegacy(
  createWithName: (
    name: string,
    items: DegreePlanItemInput[],
  ) => Promise<DegreePlanDto>,
): Promise<void> {
  if (typeof window === "undefined") return
  const raw = window.localStorage.getItem(LEGACY_KEY)
  if (!raw) return

  const existing = await degreePlanService.list()
  if (existing.meta.total > 0) {
    window.localStorage.removeItem(LEGACY_KEY)
    return
  }

  let parsed: LegacyState
  try {
    parsed = JSON.parse(raw)
  } catch {
    window.localStorage.removeItem(LEGACY_KEY)
    return
  }

  const legacyDrafts = parsed.drafts ?? []
  let activeDraftId = ""
  for (const [index, draft] of legacyDrafts.entries()) {
    const items: DegreePlanItemInput[] = []
    for (const [semester, courses] of Object.entries(draft.plan ?? {})) {
      for (const course of courses) {
        if (!course.code) continue
        items.push({
          course_code: course.code,
          planned_semester: Number(semester),
        })
      }
    }
    const created = await createWithName(
      draft.name || `Draft ${index + 1}`,
      items,
    )
    if (
      legacyDrafts[index] &&
      parsed.activeDraftId === legacyDrafts[index].name
    ) {
      activeDraftId = created.id
    }
    if (index === 0 && !activeDraftId) activeDraftId = created.id
  }

  const invalid = legacyDrafts.some((draft) =>
    Object.values(draft.plan ?? {})
      .flat()
      .some((course) => !course.code),
  )
  if (activeDraftId) {
    await degreePlanService.update(activeDraftId, { status: "active" })
  }
  if (!invalid) {
    window.localStorage.removeItem(LEGACY_KEY)
  }
}

function toCourse(item: PlannerCatalogItemDto, index: number): Course {
  return normalizeCourse({
    code: item.code ?? item.id,
    fallbackId: `mk-${index + 1}`,
    name: item.name,
    credits: item.credits,
    semester: item.semester,
    type: item.type,
    parity: item.parity,
    desc: item.desc,
    program: item.program ?? "",
  })
}
