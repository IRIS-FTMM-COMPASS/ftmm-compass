interface DevAccountPickerProps {
  onSelect: (identifier: string, password: string) => void
}

interface DemoAccount {
  label: string
  localPart?: string
  email?: string
}

const DEV_ACCOUNT_PICKER_ENABLED = true

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

const PJ_ACCOUNTS: DemoAccount[] = [
  { label: "TSD", email: "dwi.rantini@ftmm.unair.ac.id" },
  { label: "TRKB", email: "asif.ali@ftmm.unair.ac.id" },
  { label: "RN", email: "mirza.ardella@ftmm.unair.ac.id" },
  { label: "TI", email: "chandrawati.p.w@ftmm.unair.ac.id" },
  { label: "TE", email: "agus.mukhlisin@ftmm.unair.ac.id" },
]

const ADMIN_ACCOUNTS: DemoAccount[] = [{ label: "Admin", localPart: "admin" }]

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

export default function DevAccountPicker({ onSelect }: DevAccountPickerProps) {
  if (!import.meta.env.DEV || !DEV_ACCOUNT_PICKER_ENABLED) return null

  return (
    <div className="mt-5 space-y-2 rounded-xl border border-border bg-background p-3">
      <p className="text-[11px] font-semibold text-muted">Akun demo (dev)</p>
      <AccountGroup
        label="Mahasiswa"
        accounts={MAHASISWA_ACCOUNTS}
        password={MAHASISWA_PASSWORD}
        onSelect={onSelect}
      />
      <AccountGroup
        label="PJ Prodi"
        accounts={PJ_ACCOUNTS}
        password={PJ_PASSWORD}
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
