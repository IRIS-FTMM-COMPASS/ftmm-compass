import { useCallback, useEffect, useRef, useState, type FormEvent } from "react"
import { apiErrorMessage, apiFieldErrors } from "@/shared/api/client"
import { useDiscardGuard } from "@/shared/hooks/useDiscardGuard"
import {
  schedulingService,
  type BoardClassItem,
  type ClassMoveRequest,
  type FinalizeResponse,
  type GenerateResponse,
} from "../schedulingService"

export type SchedulingBusyAction = "regenerate" | "full_reset" | "finalize" | "unlock" | "edit"
export type SchedulingConfirmAction = "reset" | "unlock" | null

export interface ClassEditDraft {
  item: BoardClassItem
  day_of_week: number
  start_hour: number
  room_id: string
  reason: string
}

interface UseSchedulingActionsArgs {
  isAdmin: boolean
  isPjProdi: boolean
  canGenerate: boolean
  generationTargetProgramId?: string
  finalizeBlockers: string[]
  periodId: string
  canEditClass: (item: BoardClassItem) => boolean
  loadBoard: (options?: { silent?: boolean }) => Promise<void>
  refreshSchedulingStatus: () => void
}

export function useSchedulingActions({
  isAdmin,
  isPjProdi,
  canGenerate,
  generationTargetProgramId,
  finalizeBlockers,
  periodId,
  canEditClass,
  loadBoard,
  refreshSchedulingStatus,
}: UseSchedulingActionsArgs) {
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionNotice, setActionNotice] = useState<string | null>(null)
  const [editRoomError, setEditRoomError] = useState<string | null>(null)
  const [generationResult, setGenerationResult] =
    useState<GenerateResponse | null>(null)
  const [finalizeResult, setFinalizeResult] = useState<FinalizeResponse | null>(
    null,
  )
  const [busyAction, setBusyAction] = useState<SchedulingBusyAction | null>(
    null,
  )
  const [confirmAction, setConfirmAction] =
    useState<SchedulingConfirmAction>(null)
  const [editDraft, setEditDraft] = useState<ClassEditDraft | null>(null)
  const generationKeysRef =
    useRef<Partial<Record<"regenerate" | "full_reset", string>>>({})

  const editDirty =
    editDraft !== null &&
    (editDraft.day_of_week !== editDraft.item.day_of_week ||
      editDraft.start_hour !== editDraft.item.start_hour ||
      editDraft.room_id !== (editDraft.item.room_id ?? "") ||
      editDraft.reason !== "")
  const closeEditDraft = useCallback(() => setEditDraft(null), [])
  const { requestClose: requestCloseEdit, discardDialog } = useDiscardGuard({
    dirty: editDirty,
    onClose: closeEditDraft,
  })

  useEffect(() => {
    if (!editDraft) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return
      event.preventDefault()
      requestCloseEdit()
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [editDraft, requestCloseEdit])

  const runGenerate = async (mode: "regenerate" | "full_reset") => {
    if (!canGenerate || busyAction || !periodId) return
    if (mode === "full_reset" && !isAdmin) return
    const targetProgramId = generationTargetProgramId
    if (mode === "regenerate" && isPjProdi && !targetProgramId) return
    const requestKey =
      generationKeysRef.current[mode] ??
      (generationKeysRef.current[mode] = crypto.randomUUID())
    setBusyAction(mode)
    setActionError(null)
    setActionNotice(null)
    setFinalizeResult(null)
    try {
      const result = await schedulingService.generate({
        academic_period_id: periodId,
        mode,
        confirm_full_reset: mode === "full_reset",
        study_program_id: targetProgramId,
        request_key: requestKey,
      })
      setGenerationResult(result)
      setActionNotice(
        mode === "full_reset"
          ? "Reset penuh jadwal selesai."
          : "Jadwal berhasil dibuat ulang.",
      )
      setConfirmAction(null)
      await loadBoard()
    } catch (cause) {
      setActionError(
        apiErrorMessage(cause, "Penjadwalan otomatis gagal dijalankan."),
      )
    } finally {
      delete generationKeysRef.current[mode]
      setBusyAction(null)
    }
  }

  const runFinalize = async () => {
    if (!isPjProdi || !periodId || busyAction || finalizeBlockers.length > 0) {
      return
    }
    setBusyAction("finalize")
    setActionError(null)
    setActionNotice(null)
    setGenerationResult(null)
    try {
      const result = await schedulingService.finalize(periodId)
      setFinalizeResult(result)
      setActionNotice(
        result.all_final
          ? "Seluruh jadwal program studi telah final."
          : "Jadwal program studi telah difinalisasi.",
      )
      await loadBoard()
      refreshSchedulingStatus()
      window.dispatchEvent(new CustomEvent("scheduling-status-changed"))
    } catch (cause) {
      setActionError(apiErrorMessage(cause, "Finalisasi jadwal gagal."))
    } finally {
      setBusyAction(null)
    }
  }

  const runUnlock = async (reason: string) => {
    if (!isAdmin || !periodId || busyAction) return
    setBusyAction("unlock")
    setActionError(null)
    setActionNotice(null)
    setGenerationResult(null)
    setFinalizeResult(null)
    try {
      const result = await schedulingService.unlock(periodId, {
        reason,
        confirm: true,
      })
      setConfirmAction(null)
      setActionNotice(
        `${result.unlocked_count} jadwal dibuka. ${result.audit_count} catatan audit dibuat.`,
      )
      await loadBoard()
      refreshSchedulingStatus()
      window.dispatchEvent(new CustomEvent("scheduling-status-changed"))
    } catch (cause) {
      setActionError(apiErrorMessage(cause, "Kunci jadwal gagal dibuka."))
    } finally {
      setBusyAction(null)
    }
  }

  const openEdit = (item: BoardClassItem) => {
    if (!canEditClass(item)) return
    setActionError(null)
    setEditRoomError(null)
    setActionNotice(null)
    setGenerationResult(null)
    setFinalizeResult(null)
    setEditDraft({
      item,
      day_of_week: item.day_of_week,
      start_hour: item.start_hour,
      room_id: item.room_id ?? "",
      reason: "",
    })
  }

  const openConfirm = (action: Exclude<SchedulingConfirmAction, null>) => {
    setActionError(null)
    setConfirmAction(action)
  }

  const submitEdit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!editDraft || busyAction || !canEditClass(editDraft.item)) return
    setBusyAction("edit")
    setActionError(null)
    setEditRoomError(null)
    setActionNotice(null)
    setGenerationResult(null)
    setFinalizeResult(null)

    const request: ClassMoveRequest = {
      day_of_week: editDraft.day_of_week,
      start_hour: editDraft.start_hour,
      room_id: editDraft.room_id,
      reason: editDraft.reason.trim(),
    }
    try {
      const result = await schedulingService.moveClass(
        editDraft.item.class_section_id,
        request,
      )
      setEditDraft(null)
      setActionNotice(
        result.conflicts.length > 0
          ? `Jadwal kelas tersimpan, tetapi ${result.conflicts.length} bentrok masih terdeteksi.`
          : "Perubahan jadwal kelas tersimpan.",
      )
      await loadBoard()
    } catch (cause) {
      const roomIssue = apiFieldErrors(cause).find(
        (issue) => issue.field === "room_id" || issue.field === "room",
      )
      setEditRoomError(roomIssue?.message ?? null)
      setActionError(apiErrorMessage(cause, "Perubahan jadwal gagal disimpan."))
    } finally {
      setBusyAction(null)
    }
  }

  return {
    actionError,
    actionNotice,
    editRoomError,
    setEditRoomError,
    generationResult,
    setGenerationResult,
    finalizeResult,
    busyAction,
    confirmAction,
    setConfirmAction,
    editDraft,
    setEditDraft,
    runGenerate,
    runFinalize,
    runUnlock,
    openEdit,
    openConfirm,
    submitEdit,
    requestCloseEdit,
    discardDialog,
  }
}
