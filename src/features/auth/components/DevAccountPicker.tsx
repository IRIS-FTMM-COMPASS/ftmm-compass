import { useState } from "react"
import SearchableCombobox, {
  type ComboboxOption,
} from "@/shared/ui/SearchableCombobox"
import {
  LECTURER_ACCOUNTS,
  LECTURER_PASSWORD,
  type LecturerAccount,
} from "./lecturerAccounts"

interface DevAccountPickerProps {
  onSelect: (identifier: string, password: string) => void
  disabled?: boolean
}

interface DemoAccount {
  label: string
  localPart?: string
  email?: string
}

const DOMAIN = "@ftmm.unair.ac.id"
const MAHASISWA_PASSWORD = "Mahasiswa2026!"
const PJ_PASSWORD = "PjProdi2026!"
const ADMIN_PASSWORD = "AdminFTMM2026!"

const MAHASISWA_ACCOUNTS: DemoAccount[] = [
  { label: "TSD", localPart: "mahasiswa.tsd" },
  { label: "TRKB", localPart: "mahasiswa.trkb" },
  { label: "RN", localPart: "mahasiswa.rn" },
  { label: "TI", localPart: "mahasiswa.ti" },
  { label: "TE", localPart: "mahasiswa.te" },
  { label: "Budi", localPart: "mahasiswa.testing" },
]

const ADMIN_ACCOUNTS: DemoAccount[] = [{ label: "Admin", localPart: "admin" }]

const lecturerOption = (lecturer: LecturerAccount): ComboboxOption => ({
  value: lecturer.email,
  label: lecturer.name,
  hint: `${lecturer.prodi}, ${
    lecturer.isCoordinator ? "Koordinator" : lecturer.nip
  }`,
})

const LECTURER_OPTIONS: ComboboxOption[] = LECTURER_ACCOUNTS.map(lecturerOption)

const BUTTON_CLASS =
  "min-h-8 px-2 rounded-md border border-border bg-surface text-[11px] font-medium text-navy hover:bg-navy/5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy"

interface AccountGroupProps {
  label: string
  accounts: DemoAccount[]
  password: string
  onSelect: (identifier: string, password: string) => void
}

function AccountGroup({
  label,
  accounts,
  password,
  onSelect,
}: AccountGroupProps) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] font-semibold text-muted">{label}</span>
      {accounts.map((account) => (
        <button
          key={account.email ?? account.localPart}
          type="button"
          onClick={() =>
            onSelect(account.email ?? `${account.localPart}${DOMAIN}`, password)
          }
          className={BUTTON_CLASS}
        >
          {account.label}
        </button>
      ))}
    </div>
  )
}

export default function DevAccountPicker({
  onSelect,
  disabled = false,
}: DevAccountPickerProps) {
  const [lecturerEmail, setLecturerEmail] = useState("")

  if (
    !import.meta.env.DEV ||
    import.meta.env.VITE_DEV_ACCOUNT_PICKER === "false"
  )
    return null

  const handleLecturerSelect = (email: string) => {
    const lecturer = LECTURER_ACCOUNTS.find((item) => item.email === email)
    if (!lecturer) return
    setLecturerEmail(email)
    onSelect(
      lecturer.email,
      lecturer.isCoordinator ? PJ_PASSWORD : LECTURER_PASSWORD,
    )
  }

  return (
    <div className="mt-5 space-y-2 rounded-xl border border-border bg-background p-3">
      <p className="text-[11px] font-semibold text-muted">Akun demo (dev)</p>
      <SearchableCombobox
        id="dev-lecturer-account"
        label="Dosen"
        options={LECTURER_OPTIONS}
        value={lecturerEmail}
        onChange={handleLecturerSelect}
        placeholder="Pilih dosen"
        searchPlaceholder="Cari nama, prodi, atau NIP"
        emptyLabel="Dosen tidak ditemukan."
        disabled={disabled}
      />
      <AccountGroup
        label="Mahasiswa"
        accounts={MAHASISWA_ACCOUNTS}
        password={MAHASISWA_PASSWORD}
        onSelect={onSelect}
      />
      <AccountGroup
        label="Admin"
        accounts={ADMIN_ACCOUNTS}
        password={ADMIN_PASSWORD}
        onSelect={onSelect}
      />
    </div>
  )
}
