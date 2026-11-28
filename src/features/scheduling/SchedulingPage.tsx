import { useEffect, useMemo, useState } from "react"
import { AlertCircle } from "lucide-react"
import { useSession } from "@/features/auth/session"
import ConfirmDialog, {
  type ConfirmDialogValues,
} from "@/shared/ui/ConfirmDialog"
import type { ComboboxOption } from "@/shared/ui/SearchableCombobox"
import BoardGrid from "./components/BoardGrid"
import ClassEditSection from "./components/ClassEditSection"
import SchedulingConflictSection from "./components/SchedulingConflictSection"
import SchedulingControls from "./components/SchedulingControls"
import SchedulingDiagnosticsSection from "./components/SchedulingDiagnosticsSection"
import SchedulingLifecycleStatus from "./components/SchedulingLifecycleStatus"
import SchedulingPageHeader, {
  type SchedulingTabId,
} from "./components/SchedulingPageHeader"
import RoomAdminPanel from "./components/RoomAdminPanel"
import PreferenceDeadlinePanel from "./components/PreferenceDeadlinePanel"
import UnassignedDiagnosticDialog from "./components/UnassignedDiagnosticDialog"
import { useSchedulingStatus } from "./hooks/useSchedulingStatus"
import { useSchedulingBoard } from "./hooks/useSchedulingBoard"
import { useSchedulingActions } from "./hooks/useSchedulingActions"
import { buildSchedulingModel, type ClassScope } from "./boardModel"
import type { UnassignedItem } from "./schedulingService"

interface SchedulingPageProps {
  onOpenPanel?: (
    target: "teaching-team" | "class-assignment",
    params: {
      period?: string | null
      course?: string | null
      reference?: string | null
    },
  ) => void
}

export default function SchedulingPage({ onOpenPanel }: SchedulingPageProps) {
  const { user } = useSession()
  const { isFinal, retry: refreshSchedulingStatus } = useSchedulingStatus()
  const { board, rooms, isLoading, loadError, loadBoard, reload } =
    useSchedulingBoard(
      user?.role === "admin" ||
        (user?.role === "lecturer" && user.is_program_coordinator === true),
    )
  const [selectedProgramId, setSelectedProgramId] = useState("")
  const [classScope, setClassScope] = useState<ClassScope>("all")
  const [activeTab, setActiveTab] = useState<SchedulingTabId>("board")
  const [diagnosticItem, setDiagnosticItem] = useState<UnassignedItem | null>(
    null,
  )

  const model = useMemo(
    () =>
      buildSchedulingModel({
        board,
        user,
        selectedProgramId,
        classScope,
        isFinal,
      }),
    [board, user, selectedProgramId, classScope, isFinal],
  )

  const actions = useSchedulingActions({
    isAdmin: model.isAdmin,
    isPjProdi: model.isPjProdi,
    canGenerate: model.canGenerate,
    generationTargetProgramId: model.generationTargetProgramId,
    finalizeBlockers: model.finalizeBlockers,
    periodId: model.periodId,
    canEditClass: model.canEditClass,
    loadBoard,
    refreshSchedulingStatus,
  })

  useEffect(() => {
    if (!model.canOperateSchedule) setActiveTab("board")
  }, [model.canOperateSchedule])

  useEffect(() => {
    if (!board) return
    actions.setGenerationResult((current) => {
      if (!current) return current
      const program = current.study_program_id
        ? board.data.programs.find(
            (item) => item.study_program_id === current.study_program_id,
          )
        : undefined
      const revision = program?.input_revision ?? board.meta.input_revision
      return current.input_revision === revision ? current : null
    })
  }, [board, actions.setGenerationResult])

  const roomOptions = useMemo<ComboboxOption[]>(
    () => [
      { value: "", label: "Tanpa ruangan" },
      ...rooms
        .filter((room) => room.is_active)
        .map((room) => ({
          value: room.room_id,
          label: `${room.room_code}, ${room.capacity} kursi`,
        })),
    ],
    [rooms],
  )

  const generationProgram = actions.generationResult?.study_program_id
    ? model.programLabels.get(actions.generationResult.study_program_id)
    : null
  const generationScopeLabel = actions.generationResult
    ? generationProgram
      ? [generationProgram.code, generationProgram.name]
          .filter(Boolean)
          .join(" ")
      : "semua program studi"
    : null

  const openMappingForUnassigned = (item: UnassignedItem) => {
    const contexts = item.eligible_curriculum_contexts
    const actorContexts =
      model.isPjProdi && model.actorStudyProgramId
        ? contexts.filter(
            (context) => context.study_program_id === model.actorStudyProgramId,
          )
        : contexts
    const context =
      actorContexts.find(
        (candidate) =>
          item.pjmk_reference_id !== null &&
          candidate.pjmk_reference_id === item.pjmk_reference_id,
      ) ??
      actorContexts[0] ??
      contexts.find(
        (candidate) =>
          item.pjmk_reference_id !== null &&
          candidate.pjmk_reference_id === item.pjmk_reference_id,
      ) ??
      contexts[0]
    if (!context || !model.periodId) {
      setDiagnosticItem(item)
      return
    }
    onOpenPanel?.("teaching-team", {
      period: model.periodId,
      course: context.curriculum_course_id,
      reference: item.pjmk_reference_id,
    })
  }

  const openAssignmentForUnassigned = (item: UnassignedItem) => {
    if (!model.periodId || item.eligible_curriculum_contexts.length === 0) {
      setDiagnosticItem(item)
      return
    }
    onOpenPanel?.("class-assignment", {
      period: model.periodId,
      course:
        item.eligible_curriculum_contexts.length === 1
          ? item.eligible_curriculum_contexts[0].curriculum_course_id
          : null,
    })
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <SchedulingPageHeader
        periodLabel={board?.data.period_label}
        scopeLabel={model.scopeLabel}
        canOperateSchedule={model.canOperateSchedule}
        statusLabel={model.statusLabel}
        isCurrentScopeFinal={model.isCurrentScopeFinal}
        isAdmin={model.isAdmin}
        isPjProdi={model.isPjProdi}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onReload={reload}
      />

      {isLoading && (
        <div
          role="status"
          className="flex flex-col items-center gap-3 rounded-xl border border-border bg-surface py-12 text-muted"
        >
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gold/30 border-t-gold" />
          <p className="font-mono text-xs">Memuat papan jadwal...</p>
        </div>
      )}

      {!isLoading && loadError && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy sm:flex-row sm:items-center sm:justify-between"
        >
          <span className="flex items-center gap-2">
            <AlertCircle
              className="h-4 w-4 shrink-0 text-orange"
              aria-hidden="true"
            />
            {loadError}
          </span>
          <button
            type="button"
            onClick={reload}
            className="min-h-11 rounded-lg border border-orange/40 px-3 text-xs font-semibold text-orange transition-colors hover:bg-orange/20 cursor-pointer"
          >
            Coba lagi
          </button>
        </div>
      )}

      {model.canOperateSchedule && actions.actionError && (
        <div
          role="alert"
          className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-2.5 text-xs text-navy"
        >
          {actions.actionError}
        </div>
      )}
      {model.canOperateSchedule && actions.actionNotice && (
        <div
          role="status"
          className="rounded-xl border border-teal/40 bg-teal/15 px-4 py-2.5 text-xs text-navy"
        >
          {actions.actionNotice}
        </div>
      )}

      <div
        role="tabpanel"
        id="scheduling-panel-board"
        aria-labelledby="scheduling-tab-board"
        hidden={activeTab !== "board"}
        className="space-y-6"
      >
        {activeTab === "board" && !isLoading && !loadError && (
          <>
            {model.canOperateSchedule && (
              <SchedulingLifecycleStatus
                staleCount={model.staleCount}
                inputRevision={model.inputRevision}
                stalePrograms={model.stalePrograms}
                staleClasses={model.staleClasses}
                generationResult={actions.generationResult}
                finalizeResult={actions.finalizeResult}
                generationScopeLabel={generationScopeLabel}
              />
            )}

            <SchedulingControls
              model={model}
              selectedProgramId={selectedProgramId}
              classScope={classScope}
              busyAction={actions.busyAction}
              onSelectProgram={setSelectedProgramId}
              onSelectClassScope={setClassScope}
              onRegenerate={() => void actions.runGenerate("regenerate")}
              onFullReset={() => actions.openConfirm("reset")}
              onFinalize={() => void actions.runFinalize()}
              onUnlock={() => actions.openConfirm("unlock")}
            />

            {model.canOperateSchedule && actions.editDraft && (
              <ClassEditSection
                draft={actions.editDraft}
                roomOptions={roomOptions}
                busy={actions.busyAction !== null}
                roomError={actions.editRoomError}
                onChange={actions.setEditDraft}
                onClearRoomError={() => actions.setEditRoomError(null)}
                onSubmit={(event) => void actions.submitEdit(event)}
                onRequestClose={actions.requestCloseEdit}
              />
            )}

            <div className="space-y-3">
              {model.canOperateSchedule &&
                model.allClasses.length > 0 &&
                model.allClasses.every((item) => !item.day_of_week) && (
                  <div
                    role="alert"
                    className="flex items-center gap-2 rounded-xl border border-orange/30 bg-orange/10 px-4 py-2.5 text-xs text-navy"
                  >
                    <AlertCircle
                      className="h-4 w-4 shrink-0 text-orange"
                      aria-hidden="true"
                    />
                    Jadwal ada tetapi belum memiliki hari; muat ulang setelah
                    perbaikan backend.
                  </div>
                )}
              <BoardGrid
                classes={model.allClasses}
                conflicts={board?.data.conflicts ?? []}
                selectedProgramId={selectedProgramId || null}
                mineOnly={model.isOrdinaryLecturer && classScope === "mine"}
                assignedLecturerId={user?.user_id ?? null}
                canEditClass={model.canEditClass}
                onEditClass={actions.openEdit}
              />
            </div>

            {model.canOperateSchedule && (
              <>
                <SchedulingConflictSection rows={model.visibleConflictRows} />
                <SchedulingDiagnosticsSection
                  items={model.scopedUnassigned}
                  onMapping={openMappingForUnassigned}
                  onAssignment={openAssignmentForUnassigned}
                  onDiagnostic={setDiagnosticItem}
                />
              </>
            )}
          </>
        )}
      </div>

      <div
        role="tabpanel"
        id="scheduling-panel-rooms"
        aria-labelledby="scheduling-tab-rooms"
        hidden={activeTab !== "rooms"}
        className="rounded-xl border border-border bg-surface p-4"
      >
        {activeTab === "rooms" && model.isAdmin && <RoomAdminPanel />}
      </div>
      <div
        role="tabpanel"
        id="scheduling-panel-deadlines"
        aria-labelledby="scheduling-tab-deadlines"
        hidden={activeTab !== "deadlines"}
        className="rounded-xl border border-border bg-surface p-4"
      >
        {activeTab === "deadlines" && (model.isAdmin || model.isPjProdi) && (
          <PreferenceDeadlinePanel />
        )}
      </div>

      {diagnosticItem && (
        <UnassignedDiagnosticDialog
          item={diagnosticItem}
          onClose={() => setDiagnosticItem(null)}
        />
      )}

      {actions.discardDialog}

      {actions.confirmAction === "reset" && (
        <ConfirmDialog
          title="Reset dan generate ulang jadwal?"
          body={
            <p className="text-xs text-muted">
              Penjadwalan draf untuk {model.actionScopeLabel} akan dibuat ulang.
              Periksa cakupan dan hasilnya sebelum finalisasi.
            </p>
          }
          confirmLabel="Reset & generate"
          tone="orange"
          busy={actions.busyAction === "full_reset"}
          errorMessage={actions.actionError}
          manualField={{
            expected: "RESET",
            label: "Ketik RESET untuk mengonfirmasi",
            placeholder: "RESET",
          }}
          onConfirm={() => void actions.runGenerate("full_reset")}
          onCancel={() => actions.setConfirmAction(null)}
        />
      )}

      {actions.confirmAction === "unlock" && (
        <ConfirmDialog
          title="Buka kunci jadwal?"
          body={
            <p className="text-xs text-muted">
              Jadwal yang telah final dapat diubah kembali setelah kunci dibuka.
            </p>
          }
          confirmLabel="Buka kunci"
          tone="orange"
          busy={actions.busyAction === "unlock"}
          errorMessage={actions.actionError}
          reasonField={{ required: true, label: "Alasan pembukaan kunci" }}
          onConfirm={(values: ConfirmDialogValues) =>
            void actions.runUnlock(values.reason)
          }
          onCancel={() => actions.setConfirmAction(null)}
        />
      )}
    </div>
  )
}
