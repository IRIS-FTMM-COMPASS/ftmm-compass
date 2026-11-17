import { useCallback, useEffect, useRef, useState } from "react"
import type { Dispatch, SetStateAction } from "react"
import { apiErrorMessage } from "@/shared/api/client"

export interface ReloadableResource<T> {
  data: T | null
  status: "loading" | "ready" | "error"
  error: string | null
  reload: () => void
  update: Dispatch<SetStateAction<T | null>>
}

export function useReloadableFetch<T>(
  load: (signal: AbortSignal) => Promise<T> | null,
  dependencies: readonly unknown[],
  fallbackMessage: string,
  emptyValue: T | null = null,
): ReloadableResource<T> {
  const [data, setData] = useState<T | null>(emptyValue)
  const [status, setStatus] =
    useState<ReloadableResource<T>["status"]>("loading")
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
  const loadRef = useRef(load)
  loadRef.current = load

  const reload = useCallback(() => setReloadToken((token) => token + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    const request = loadRef.current(controller.signal)
    if (request === null) {
      setData(emptyValue)
      setStatus("ready")
      setError(null)
      return
    }

    setStatus("loading")
    setError(null)
    request
      .then((result) => {
        if (controller.signal.aborted) return
        setData(result)
        setStatus("ready")
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setError(apiErrorMessage(reason, fallbackMessage))
        setStatus("error")
      })
    return () => controller.abort()
  }, [...dependencies, reloadToken])

  return { data, status, error, reload, update: setData }
}
