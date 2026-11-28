import { useCallback, useEffect, useRef, useState } from "react"
import { apiErrorMessage } from "@/shared/api/client"
import {
  schedulingService,
  type BoardResponse,
  type RoomResponse,
} from "../schedulingService"

const BOARD_POLL_INTERVAL_MS = 5_000

export function useSchedulingBoard(canOperateSchedule: boolean) {
  const [board, setBoard] = useState<BoardResponse | null>(null)
  const [rooms, setRooms] = useState<RoomResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const boardLoadCount = useRef(0)

  const loadBoard = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true
    if (!silent) setIsLoading(true)
    boardLoadCount.current += 1
    try {
      const response = await schedulingService.getBoard()
      setBoard(response)
      setLoadError(null)
    } catch (cause) {
      if (!silent) {
        setLoadError(apiErrorMessage(cause, "Papan jadwal tidak dapat dimuat."))
      }
    } finally {
      boardLoadCount.current -= 1
      if (!silent) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadBoard()
  }, [loadBoard, reloadKey])

  useEffect(() => {
    let active = true
    const intervalId = window.setInterval(() => {
      if (!active || boardLoadCount.current > 0) return
      void loadBoard({ silent: true })
    }, BOARD_POLL_INTERVAL_MS)
    return () => {
      active = false
      window.clearInterval(intervalId)
    }
  }, [loadBoard])

  useEffect(() => {
    if (!canOperateSchedule) return
    let active = true
    schedulingService
      .listRooms()
      .then((items) => {
        if (active) setRooms(items)
      })
      .catch(() => {
        if (active) setRooms([])
      })
    return () => {
      active = false
    }
  }, [canOperateSchedule])

  const reload = useCallback(() => setReloadKey((key) => key + 1), [])

  return { board, rooms, isLoading, loadError, loadBoard, reload }
}
