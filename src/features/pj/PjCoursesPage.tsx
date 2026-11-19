import { useEffect, useState } from "react"
import { AlertCircle, CheckCircle2, Lock, RefreshCw } from "lucide-react"
import { useSession } from "@/features/auth/session"
import { usePolling } from "@/features/polling/polling"
import {
  pjService,
  type PjAvailabilityItem,
  type PjAvailabilityMeta,
} from "@/features/polling/pollingService"
import { useDemandAnalytics } from "@/features/dashboard/hooks/useDemandAnalytics"
import PollingPanel from "@/features/dashboard/components/PollingPanel"
import ConfirmDialog, {
  type ConfirmDialogValues,
} from "@/shared/ui/ConfirmDialog"
import { apiErrorMessage } from "@/shared/api/client"
import { cn } from "@/shared/utils"

interface PjCoursesPageProps {
  onNavigate: (page: string) => void
}

const LOCK_REASON_LABELS: Record<string, string> = {
  semester_berjalan: "Semester berjalan — perubahan terkunci",
  bukan_pilihan: "Bukan MK Pilihan",
  dinonaktifkan: "MK sudah dinonaktifkan",
}

const SCOPE_LABELS: Record<string, string> = {
  program_studi: "Program Studi",
  fakultas: "Fakultas",
  universitas: "Universitas",
}

function lockReasonLabel(reason: string | null | undefined): string {
  if (!reason) return ""
  return LOCK_REASON_LABELS[reason] ?? reason.replace(/_/g, " ")
}

export default function PjCoursesPage({ onNavigate }: PjCoursesPageProps) {
  const { user } = useSession()
  const { period: pollingPeriod, myVotes, error: pollingError } = usePolling()
  const {
    selectedProdi,
    setSelectedProdi,
    demandAnalytics,
    items: demandItems,
    isLoadingAnalytics,
    handleExportCSV,
  } = useDemandAnalytics(user)

  const [items, setItems] = useState<PjAvailabilityItem[]>([])
  const [meta, setMeta] = useState<PjAvailabilityMeta | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [pending, setPending] = useState<PjAvailabilityItem | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setIsLoading(true)
    setLoadError(null)
    pjService
      .getAvailability()
      .then((result) => {
        if (!active) return
        setItems(result.data)
        setMeta(result.meta)
      })
      .catch((cause) => {
        if (active) {
          setLoadError(
            apiErrorMessage(cause, "Daftar mata kuliah tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [reloadKey])

  const confirmToggle = async (values: ConfirmDialogValues) => {
    if (!pending || !pending.can_toggle) return
    setSavingId(pending.curriculum_course_id)
    setActionError(null)
    try {
      const updated = await pjService.setAvailability(
        pending.curriculum_course_id,
        !pending.is_active,
        values.reason || undefined,
      )
      setItems((prev) =>
        prev.map((item) =>
          item.curriculum_course_id === updated.curriculum_course_id
            ? updated
            : item,
        ),
      )
      setPending(null)
    } catch (cause) {
      setActionError(
        apiErrorMessage(cause, "Perubahan ketersediaan gagal disimpan."),
      )
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <section aria-labelledby="pj-rekap-title" className="space-y-3">
        <div>
          <h2
            id="pj-rekap-title"
            className="font-heading text-lg font-bold text-navy md:text-xl"
          >
            Rekap Peminatan
          </h2>
          <p className="text-xs text-muted">
            Analisis peminatan MK Pilihan untuk program studi yang Anda kelola
            sebagai PJ Prodi.
          </p>
        </div>
        {pollingError && (
          <div
            role="status"
            className="rounded-xl border border-orange/30 bg-orange/10 px-4 py-2.5 text-xs text-navy"
          >
            {pollingError}
          </div>
        )}
        <PollingPanel
          user={user}
          studentVotes={myVotes}
          pollingPeriod={pollingPeriod}
          onNavigate={onNavigate}
          selectedProdi={selectedProdi}
          setSelectedProdi={setSelectedProdi}
          items={demandItems}
          demandAnalytics={demandAnalytics}
          isLoadingAnalytics={isLoadingAnalytics}
          handleExportCSV={handleExportCSV}
        />
      </section>

      <section aria-labelledby="pj-kelola-title" className="space-y-3">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h2
              id="pj-kelola-title"
              className="font-heading text-lg font-bold text-navy md:text-xl"
            >
              Kelola Ketersediaan Mata Kuliah
            </h2>
            <p className="text-xs text-muted">
              Tentukan MK Pilihan yang dapat dipilih mahasiswa pada periode
              polling berikutnya.
            </p>
          </div>
          {meta && (
            <p className="text-xs text-muted md:text-right">
              {meta.study_program} · Semester target {meta.target_semester} ·{" "}
              {meta.total} mata kuliah
            </p>
          )}
        </div>

        {isLoading && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-surface py-12 text-muted">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-gold/30 border-t-gold" />
            <p className="font-mono text-xs">Memuat daftar mata kuliah...</p>
          </div>
        )}

        {!isLoading && loadError && (
          <div
            role="alert"
            className="flex flex-col gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-navy sm:flex-row sm:items-center sm:justify-between"
          >
            <span className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-orange" />
              {loadError}
            </span>
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border border-orange/40 px-3 text-xs font-semibold text-orange transition-colors hover:bg-orange/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 cursor-pointer"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Coba lagi
            </button>
          </div>
        )}

        {!isLoading && !loadError && (
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full min-w-[64rem] text-left text-xs">
              <thead className="border-b border-border bg-background font-mono text-[10px] uppercase tracking-wider text-muted">
                <tr>
                  <th scope="col" className="px-3 py-3 font-semibold">
                    Kode MK
                  </th>
                  <th scope="col" className="px-3 py-3 font-semibold">
                    Mata Kuliah
                  </th>
                  <th scope="col" className="px-3 py-3 font-semibold">
                    Prodi / Cakupan
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-3 text-center font-semibold"
                  >
                    Semester
                  </th>
                  <th scope="col" className="px-3 py-3 font-semibold">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-3 font-semibold">
                    Alasan Terkunci
                  </th>
                  <th
                    scope="col"
                    className="px-3 py-3 text-center font-semibold"
                  >
                    Aksi
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {items.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-10 text-center text-muted"
                    >
                      Tidak ada mata kuliah untuk ditampilkan pada periode ini.
                    </td>
                  </tr>
                ) : (
                  items.map((item) => {
                    const reason = lockReasonLabel(item.lock_reason)
                    const isLocked = !item.can_toggle
                    const isBusy = savingId === item.curriculum_course_id
                    const reasonId = `pj-lock-reason-${item.curriculum_course_id}`
                    return (
                      <tr
                        key={item.curriculum_course_id}
                        className={cn(
                          "transition-colors hover:bg-background/60",
                          isLocked && "bg-background/40",
                        )}
                      >
                        <td className="px-3 py-3 font-mono font-bold text-navy">
                          {item.course_code}
                        </td>
                        <td className="px-3 py-3">
                          <p className="font-medium text-foreground">
                            {item.course_name}
                          </p>
                          <p className="mt-0.5 text-[11px] text-muted">
                            {item.credits} SKS · {item.type || "Pilihan"}
                          </p>
                        </td>
                        <td className="px-3 py-3">
                          <p className="text-foreground">
                            {meta?.study_program ?? "Program Studi"}
                          </p>
                          <p className="mt-0.5 text-[11px] text-muted">
                            {SCOPE_LABELS[item.course_scope] ??
                              item.course_scope.replace(/_/g, " ")}
                          </p>
                        </td>
                        <td className="px-3 py-3 text-center font-mono text-foreground">
                          {item.semester ?? "—"}
                        </td>
                        <td className="px-3 py-3">
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                              item.is_active
                                ? "border-gold/40 bg-gold/15 text-navy"
                                : "border-border bg-secondary text-muted",
                            )}
                          >
                            {item.is_active ? (
                              <CheckCircle2 className="h-3 w-3" />
                            ) : (
                              <Lock className="h-3 w-3" />
                            )}
                            {item.is_active ? "Aktif" : "Nonaktif"}
                          </span>
                        </td>
                        <td id={reasonId} className="px-3 py-3 text-muted">
                          {reason ? (
                            <span className="inline-flex items-center gap-1.5 text-orange">
                              <Lock className="h-3.5 w-3.5 shrink-0" />
                              {reason}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-3 py-3 text-center">
                          <button
                            type="button"
                            disabled={isLocked || isBusy}
                            aria-disabled={isLocked || isBusy}
                            aria-describedby={isLocked ? reasonId : undefined}
                            title={
                              isLocked
                                ? reason || "MK ini tidak dapat diubah"
                                : item.is_active
                                  ? "Nonaktifkan mata kuliah"
                                  : "Aktifkan mata kuliah"
                            }
                            onClick={() => {
                              if (!item.can_toggle || isBusy) return
                              setActionError(null)
                              setPending(item)
                            }}
                            className={cn(
                              "inline-flex min-h-11 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border px-3 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2",
                              isLocked
                                ? "cursor-not-allowed border-border bg-secondary text-muted opacity-70"
                                : item.is_active
                                  ? "cursor-pointer border-orange/40 bg-orange/10 text-orange hover:bg-orange/20"
                                  : "cursor-pointer border-gold/40 bg-gold/15 text-navy hover:bg-gold/25",
                              isBusy && "cursor-wait opacity-60",
                            )}
                          >
                            {item.is_active ? (
                              <Lock className="h-3.5 w-3.5" />
                            ) : (
                              <CheckCircle2 className="h-3.5 w-3.5" />
                            )}
                            <span>
                              {isBusy
                                ? "Menyimpan..."
                                : item.is_active
                                  ? "Nonaktifkan"
                                  : "Aktifkan"}
                            </span>
                            {isLocked && (
                              <span className="sr-only">
                                Tidak dapat diubah: {reason || "MK terkunci"}
                              </span>
                            )}
                          </button>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {pending && (
        <ConfirmDialog
          key={pending.curriculum_course_id}
          labelledBy="pj-availability-dialog-title"
          title={
            pending.is_active
              ? "Nonaktifkan mata kuliah?"
              : "Aktifkan mata kuliah?"
          }
          body={
            <div className="space-y-2">
              <p className="text-sm text-foreground">
                {pending.course_code} — {pending.course_name}
              </p>
              <p className="text-xs text-muted">
                {pending.is_active
                  ? "MK Pilihan ini tidak dapat dipilih mahasiswa sampai PJ Prodi mengaktifkannya kembali."
                  : "MK Pilihan ini kembali tersedia untuk periode polling yang ditargetkan."}
              </p>
            </div>
          }
          confirmLabel={pending.is_active ? "Nonaktifkan" : "Aktifkan"}
          tone={pending.is_active ? "orange" : "navy"}
          reasonField={{
            required: false,
            label: "Alasan perubahan",
            placeholder: "Tuliskan alasan jika perlu",
          }}
          busy={savingId !== null}
          errorMessage={actionError}
          onConfirm={(values) => void confirmToggle(values)}
          onCancel={() => {
            setPending(null)
            setActionError(null)
          }}
        />
      )}
    </div>
  )
}
