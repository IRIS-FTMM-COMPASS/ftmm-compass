import { useEffect, useMemo, useRef, useState, type FormEvent } from "react"
import { AlertCircle, Pencil, Plus, RefreshCw } from "lucide-react"
import { useSession } from "@/features/auth/session"
import { authService } from "@/features/auth/authService"
import {
  schedulingService,
  type RoomCreateRequest,
  type RoomResponse,
} from "@/features/scheduling/schedulingService"
import { apiErrorMessage } from "@/shared/api/client"
import { cn } from "@/shared/utils"

interface RoomFormValues {
  room_code: string
  building: string
  floor: string
  capacity: string
  owner_study_program_id: string
  is_active: boolean
}

interface ProgramOption {
  id: string
  label: string
}

type FieldErrors = Partial<Record<"room_code" | "building" | "capacity", string>>

const EMPTY_FORM: RoomFormValues = {
  room_code: "",
  building: "",
  floor: "",
  capacity: "",
  owner_study_program_id: "",
  is_active: true,
}

const inputClass =
  "min-h-11 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
const buttonClass =
  "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg px-4 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer"

function validate(values: RoomFormValues): FieldErrors {
  const errors: FieldErrors = {}
  const code = values.room_code.trim()
  if (!code) {
    errors.room_code = "Kode ruangan wajib diisi."
  } else if (code.length > 50) {
    errors.room_code = "Kode ruangan maksimal 50 karakter."
  }
  if (!values.building.trim()) {
    errors.building = "Gedung wajib diisi."
  }
  if (!values.capacity.trim()) {
    errors.capacity = "Kapasitas wajib diisi."
  } else {
    const capacity = Number(values.capacity)
    if (!Number.isInteger(capacity) || capacity < 1) {
      errors.capacity = "Kapasitas harus bilangan bulat minimal 1."
    }
  }
  return errors
}

function roomLocation(room: RoomResponse): string {
  const parts: string[] = []
  if (room.building?.trim()) parts.push(room.building.trim())
  if (room.floor?.trim()) parts.push(`Lantai ${room.floor.trim()}`)
  parts.push(room.room_code)
  return parts.join(" · ")
}

function RoleNotice() {
  return (
    <section
      aria-labelledby="room-admin-title"
      className="rounded-xl border border-border bg-surface p-6 text-center"
    >
      <h2
        id="room-admin-title"
        className="font-heading text-lg font-bold text-navy"
      >
        Kelola Ruangan
      </h2>
      <p className="mx-auto mt-2 max-w-lg text-sm text-muted">
        Pengelolaan ruangan hanya tersedia bagi admin FTMM Compass. PJ Prodi
        dapat melihat ruangan yang tersedia pada Papan Jadwal Bersama.
      </p>
    </section>
  )
}

export default function RoomAdminPanel() {
  const { user } = useSession()
  const isAdmin = user?.role === "admin"

  const [rooms, setRooms] = useState<RoomResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const [accountPrograms, setAccountPrograms] = useState<ProgramOption[]>([])
  const [accountFailed, setAccountFailed] = useState(false)

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<RoomFormValues>(EMPTY_FORM)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const codeRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isAdmin) return
    let active = true
    setIsLoading(true)
    setLoadError(null)
    schedulingService
      .listRooms()
      .then((items) => {
        if (active) {
          setRooms(
            [...items].sort((a, b) => a.room_code.localeCompare(b.room_code)),
          )
        }
      })
      .catch((cause) => {
        if (active) {
          setLoadError(
            apiErrorMessage(cause, "Daftar ruangan tidak dapat dimuat."),
          )
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [isAdmin, reloadKey])

  useEffect(() => {
    if (!isAdmin) return
    let active = true
    authService
      .listAccounts({ role: "lecturer", page: 1, page_size: 100 })
      .then((result) => {
        if (!active) return
        const byId = new Map<string, string>()
        for (const account of result.items) {
          if (account.study_program_id) {
            byId.set(
              account.study_program_id,
              account.study_program?.trim() || account.study_program_id,
            )
          }
        }
        setAccountPrograms(
          Array.from(byId, ([id, label]) => ({ id, label })).sort((a, b) =>
            a.label.localeCompare(b.label),
          ),
        )
        setAccountFailed(false)
      })
      .catch(() => {
        if (active) setAccountFailed(true)
      })
    return () => {
      active = false
    }
  }, [isAdmin])

  useEffect(() => {
    if (formOpen) codeRef.current?.focus()
  }, [formOpen])

  const programOptions = useMemo(() => {
    const byId = new Map<string, string>()
    for (const option of accountPrograms) byId.set(option.id, option.label)
    for (const room of rooms) {
      if (
        room.owner_study_program_id &&
        !byId.has(room.owner_study_program_id)
      ) {
        byId.set(room.owner_study_program_id, room.owner_study_program_id)
      }
    }
    return Array.from(byId, ([id, label]) => ({ id, label })).sort((a, b) =>
      a.label.localeCompare(b.label),
    )
  }, [accountPrograms, rooms])

  const useProgramSelect = !accountFailed && programOptions.length > 0

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setEditingId(null)
    setFieldErrors({})
    setFormError(null)
    setSuccess(null)
    setFormOpen(true)
  }

  const openEdit = (room: RoomResponse) => {
    setForm({
      room_code: room.room_code,
      building: room.building ?? "",
      floor: room.floor ?? "",
      capacity: String(room.capacity),
      owner_study_program_id: room.owner_study_program_id ?? "",
      is_active: room.is_active,
    })
    setEditingId(room.room_id)
    setFieldErrors({})
    setFormError(null)
    setSuccess(null)
    setFormOpen(true)
  }

  const closeForm = () => {
    setFormOpen(false)
    setEditingId(null)
    setFormError(null)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors = validate(form)
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    const payload: RoomCreateRequest = {
      room_code: form.room_code.trim(),
      building: form.building.trim(),
      floor: form.floor.trim() || null,
      capacity: Number(form.capacity),
      owner_study_program_id: form.owner_study_program_id.trim() || null,
      is_active: form.is_active,
    }
    setIsSaving(true)
    setFormError(null)
    setSuccess(null)
    try {
      const saved = editingId
        ? await schedulingService.updateRoom(editingId, payload)
        : await schedulingService.createRoom(payload)
      setRooms((previous) => {
        const next = editingId
          ? previous.map((room) =>
              room.room_id === saved.room_id ? saved : room,
            )
          : [...previous, saved]
        return next.sort((a, b) => a.room_code.localeCompare(b.room_code))
      })
      setFormOpen(false)
      setEditingId(null)
      setForm(EMPTY_FORM)
      setSuccess(`Ruangan ${saved.room_code} berhasil disimpan.`)
    } catch (cause) {
      setFormError(apiErrorMessage(cause, "Data ruangan gagal disimpan."))
    } finally {
      setIsSaving(false)
    }
  }

  if (!isAdmin) return <RoleNotice />

  return (
    <section aria-labelledby="room-admin-title" className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2
            id="room-admin-title"
            className="font-heading text-lg font-bold text-navy md:text-xl"
          >
            Kelola Ruangan
          </h2>
          <p className="text-xs text-muted">
            Tambah ruangan dan atur gedung, lantai, kapasitas, prodi pemilik,
            serta status penggunaannya pada penjadwalan.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className={cn(
            buttonClass,
            "border border-navy bg-navy text-white hover:bg-navy-light",
          )}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Tambah ruangan
        </button>
      </div>

      {success && (
        <p
          role="status"
          className="rounded-lg border border-border bg-accent px-4 py-2.5 text-xs text-navy"
        >
          {success}
        </p>
      )}

      {formOpen && (
        <form
          noValidate
          onSubmit={handleSubmit}
          aria-labelledby="room-form-title"
          className="space-y-4 rounded-xl border border-border bg-surface p-4"
        >
          <h3
            id="room-form-title"
            className="font-heading text-base font-bold text-navy"
          >
            {editingId ? "Ubah ruangan" : "Tambah ruangan"}
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label
                htmlFor="room-code"
                className="block text-xs font-semibold text-foreground"
              >
                Kode ruangan
              </label>
              <input
                ref={codeRef}
                id="room-code"
                type="text"
                maxLength={50}
                value={form.room_code}
                onChange={(event) =>
                  setForm((previous) => ({
                    ...previous,
                    room_code: event.target.value,
                  }))
                }
                aria-invalid={Boolean(fieldErrors.room_code)}
                aria-describedby={
                  fieldErrors.room_code ? "room-code-error" : undefined
                }
                placeholder="Contoh: A-101"
                className={inputClass}
              />
              {fieldErrors.room_code && (
                <p
                  id="room-code-error"
                  role="alert"
                  className="text-xs text-orange"
                >
                  {fieldErrors.room_code}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="room-building"
                className="block text-xs font-semibold text-foreground"
              >
                Gedung
              </label>
              <input
                id="room-building"
                type="text"
                maxLength={100}
                value={form.building}
                onChange={(event) =>
                  setForm((previous) => ({
                    ...previous,
                    building: event.target.value,
                  }))
                }
                aria-invalid={Boolean(fieldErrors.building)}
                aria-describedby={
                  fieldErrors.building ? "room-building-error" : undefined
                }
                placeholder="Contoh: NANO"
                className={inputClass}
              />
              {fieldErrors.building && (
                <p
                  id="room-building-error"
                  role="alert"
                  className="text-xs text-orange"
                >
                  {fieldErrors.building}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="room-floor"
                className="block text-xs font-semibold text-foreground"
              >
                Lantai
              </label>
              <input
                id="room-floor"
                type="text"
                maxLength={20}
                value={form.floor}
                onChange={(event) =>
                  setForm((previous) => ({
                    ...previous,
                    floor: event.target.value,
                  }))
                }
                placeholder="Contoh: 6"
                className={inputClass}
              />
              <p className="text-xs text-muted">
                Kosongkan bila ruangan tidak memiliki lantai.
              </p>
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="room-capacity"
                className="block text-xs font-semibold text-foreground"
              >
                Kapasitas
              </label>
              <input
                id="room-capacity"
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                value={form.capacity}
                onChange={(event) =>
                  setForm((previous) => ({
                    ...previous,
                    capacity: event.target.value,
                  }))
                }
                aria-invalid={Boolean(fieldErrors.capacity)}
                aria-describedby={
                  fieldErrors.capacity ? "room-capacity-error" : undefined
                }
                placeholder="Minimum 1"
                className={inputClass}
              />
              {fieldErrors.capacity && (
                <p
                  id="room-capacity-error"
                  role="alert"
                  className="text-xs text-orange"
                >
                  {fieldErrors.capacity}
                </p>
              )}
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <label
                htmlFor="room-owner"
                className="block text-xs font-semibold text-foreground"
              >
                Program studi pemilik
              </label>
              {useProgramSelect ? (
                <select
                  id="room-owner"
                  value={form.owner_study_program_id}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      owner_study_program_id: event.target.value,
                    }))
                  }
                  className={inputClass}
                >
                  <option value="">Tanpa prodi pemilik</option>
                  {programOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id="room-owner"
                  type="text"
                  value={form.owner_study_program_id}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      owner_study_program_id: event.target.value,
                    }))
                  }
                  placeholder="ID program studi (opsional)"
                  className={inputClass}
                />
              )}
              <p className="text-xs text-muted">
                {useProgramSelect
                  ? "Pemilik dapat dikosongkan agar ruangan dapat dipakai semua prodi."
                  : "Daftar prodi tidak tersedia; masukkan ID program studi bila diperlukan."}
              </p>
            </div>
            <div className="sm:col-span-2">
              <label
                htmlFor="room-active"
                className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-border bg-background px-3 text-sm text-foreground"
              >
                <input
                  id="room-active"
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      is_active: event.target.checked,
                    }))
                  }
                  className="h-4 w-4 accent-navy"
                />
                Ruangan aktif digunakan
              </label>
            </div>
          </div>

          {formError && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-orange/30 bg-orange/10 px-3 py-2 text-xs text-navy"
            >
              <AlertCircle
                className="mt-0.5 h-4 w-4 shrink-0 text-orange"
                aria-hidden="true"
              />
              {formError}
            </p>
          )}

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="submit"
              disabled={isSaving}
              className={cn(
                buttonClass,
                "border border-navy bg-navy text-white hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              {isSaving ? "Menyimpan..." : "Simpan ruangan"}
            </button>
            <button
              type="button"
              onClick={closeForm}
              disabled={isSaving}
              className={cn(
                buttonClass,
                "border border-border bg-surface text-navy hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              Batal
            </button>
          </div>
        </form>
      )}

      {isLoading && (
        <div className="rounded-xl border border-border bg-surface px-4 py-10 text-center">
          <p className="font-mono text-xs text-muted">
            Memuat daftar ruangan...
          </p>
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
            onClick={() => setReloadKey((key) => key + 1)}
            className={cn(
              buttonClass,
              "border border-orange/40 bg-surface text-orange hover:bg-orange/10",
            )}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Coba lagi
          </button>
        </div>
      )}

      {!isLoading && !loadError && rooms.length === 0 && (
        <div className="rounded-xl border border-border bg-surface px-4 py-10 text-center text-sm text-muted">
          Belum ada ruangan terdaftar. Gunakan tombol Tambah ruangan untuk
          membuat ruangan pertama.
        </div>
      )}

      {!isLoading && !loadError && rooms.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-surface">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <caption className="sr-only">
              Daftar ruangan beserta gedung, lantai, kapasitas, dan statusnya
            </caption>
            <thead className="bg-secondary text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Ruangan
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Kapasitas
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Prodi pemilik
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Status
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Aksi
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rooms.map((room) => {
                const owner = room.owner_study_program_id
                  ? (programOptions.find(
                      (option) => option.id === room.owner_study_program_id,
                    )?.label ?? room.owner_study_program_id)
                  : "—"
                return (
                  <tr key={room.room_id} className="text-foreground">
                    <th scope="row" className="px-4 py-3 font-semibold">
                      {roomLocation(room)}
                    </th>
                    <td className="px-4 py-3">{room.capacity}</td>
                    <td className="max-w-52 truncate px-4 py-3" title={owner}>
                      {owner}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2.5 py-1 text-xs font-semibold",
                          room.is_active
                            ? "bg-accent text-navy"
                            : "bg-secondary text-muted",
                        )}
                      >
                        {room.is_active ? "Aktif" : "Nonaktif"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => openEdit(room)}
                        aria-label={`Ubah ruangan ${room.room_code}`}
                        className={cn(
                          buttonClass,
                          "min-w-11 border border-border bg-surface px-2.5 text-navy hover:bg-accent",
                        )}
                      >
                        <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                        Ubah
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
