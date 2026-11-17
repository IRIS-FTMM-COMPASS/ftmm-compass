export type SaveStatus = "idle" | "pending" | "saving" | "saved" | "error"

export interface SaveState {
  status: SaveStatus
  revision: number
  savedRevision: number
  lastSaved: Date | null
  error: string | null
}

interface LoadedSaveEvent {
  type: "loaded"
  revision: number
  at: Date
}

interface ClearedSaveEvent {
  type: "cleared"
}

interface EditSaveEvent {
  type: "edit"
  revision: number
}

interface StartSaveEvent {
  type: "save-start"
}

interface SuccessSaveEvent {
  type: "save-success"
  revision: number
  at: Date
}

interface FailureSaveEvent {
  type: "save-failure"
  message: string
}

interface RetrySaveEvent {
  type: "retry"
}

interface DiscardSaveEvent {
  type: "discard"
  revision: number
  at: Date
}

interface ClearErrorSaveEvent {
  type: "clear-error"
}

export type SaveEvent = LoadedSaveEvent | ClearedSaveEvent | EditSaveEvent | StartSaveEvent | SuccessSaveEvent | FailureSaveEvent | RetrySaveEvent | DiscardSaveEvent | ClearErrorSaveEvent

export interface PlanEntryRef {
  code?: string | null
  semester: number
}

export const initialSaveState: SaveState = {
  status: "idle",
  revision: 0,
  savedRevision: 0,
  lastSaved: null,
  error: null,
}

export function saveReducer(state: SaveState, event: SaveEvent): SaveState {
  switch (event.type) {
    case "loaded":
    case "discard":
      return {
        status: "saved",
        revision: event.revision,
        savedRevision: event.revision,
        lastSaved: event.at,
        error: null,
      }
    case "cleared":
      return initialSaveState
    case "edit":
      return {
        ...state,
        revision: Math.max(state.revision, event.revision),
        status: "pending",
        error: null,
      }
    case "save-start":
      return state.status === "saving"
        ? state
        : { ...state, status: "saving", error: null }
    case "save-success": {
      const savedRevision = Math.max(state.savedRevision, event.revision)
      return {
        ...state,
        savedRevision,
        status: savedRevision >= state.revision ? "saved" : "pending",
        lastSaved: event.at,
        error: null,
      }
    }
    case "save-failure":
      return { ...state, status: "error", error: event.message }
    case "clear-error":
      return {
        ...state,
        status:
          state.status === "error"
            ? hasPendingEdits(state)
              ? "pending"
              : "saved"
            : state.status,
        error: null,
      }
    case "retry":
      return state.status === "error"
        ? { ...state, status: "pending", error: null }
        : state
  }
}

export function hasPendingEdits(state: SaveState): boolean {
  return state.revision > state.savedRevision
}

export function planSignature(entries: Iterable<PlanEntryRef>): string {
  return [...entries]
    .filter((entry) => Boolean(entry.code))
    .map((entry) => `${entry.semester}:${entry.code}`)
    .sort()
    .join("|")
}

// Item order is normalized by the API, so only course placement is compared.
export function plansDiffer(
  local: Iterable<PlanEntryRef>,
  server: Iterable<PlanEntryRef>,
): boolean {
  return planSignature(local) !== planSignature(server)
}
