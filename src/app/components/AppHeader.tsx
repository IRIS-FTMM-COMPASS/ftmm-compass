import AnimatedMenuToggle from "@/app/components/AnimatedMenuToggle"
import NotificationDropdown from "@/app/components/NotificationDropdown"
import type { AuthUser } from "@/features/auth/authService"

interface PeriodLabel {
  label?: string | null
  week_label?: string | null
}

interface AppHeaderProps {
  isOpen: boolean
  onToggle: () => void
  title: string
  user: AuthUser | null
  period: PeriodLabel | null
}

export default function AppHeader({
  isOpen,
  onToggle,
  title,
  user,
  period,
}: AppHeaderProps) {
  return (
    <header className="h-16 bg-surface border-b border-border flex items-center justify-between px-4 md:px-8 flex-shrink-0 relative z-30">
      <div className="flex items-center gap-3">
        <AnimatedMenuToggle isOpen={isOpen} onClick={onToggle} />
        <h1 className="font-heading text-xl md:text-2xl font-bold text-navy capitalize truncate">
          {title}
        </h1>
      </div>
      <div className="flex items-center gap-2 md:gap-4">
        <NotificationDropdown currentUser={user} />
        <div className="text-sm text-right hidden sm:block">
          <p className="font-medium text-navy">
            {period?.label ?? "Periode akademik"}
          </p>
          <p className="text-xs text-muted font-mono">
            {period?.week_label ?? ""}
          </p>
        </div>
      </div>
    </header>
  )
}
