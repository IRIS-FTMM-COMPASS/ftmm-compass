import { LogOut, User, X } from "lucide-react"
import type { ComponentType, MouseEvent } from "react"
import { cn } from "@/shared/utils"
import BrandLogo from "@/shared/ui/BrandLogo"
import type { AuthUser } from "@/features/auth/authService"
import { pageUrlWithContext, type Page } from "@/app/routes"

interface AppSidebarProps {
  isOpen: boolean
  onClose: () => void
  navItems: readonly {
    id: string
    label: string
    icon: ComponentType<{ className?: string }>
  }[]
  visiblePage: Page
  user: AuthUser | null
  onNavigate: (event: MouseEvent<HTMLAnchorElement>, page: Page) => void
  onLogoutRequest: () => void
}

export default function AppSidebar({
  isOpen,
  onClose,
  navItems,
  visiblePage,
  user,
  onNavigate,
  onLogoutRequest,
}: AppSidebarProps) {
  return (
    <aside
      inert={!isOpen}
      aria-hidden={!isOpen}
      className={cn(
        "bg-navy text-white flex flex-col flex-shrink-0 shadow-xl z-20 transition-all duration-300 ease-in-out absolute lg:relative h-full overflow-hidden",
        isOpen
          ? "w-64 translate-x-0 opacity-100"
          : "w-0 -translate-x-full lg:translate-x-0 opacity-0 pointer-events-none",
      )}
    >
      <div className="flex flex-col h-full w-64 min-w-[16rem]">
        <button
          onClick={onClose}
          aria-label="Tutup menu"
          className="lg:hidden absolute top-4 right-4 min-h-11 min-w-11 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors z-10 cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-5 pb-3">
          <BrandLogo variant="sidebar" />
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2 border-t border-navy-light/50">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = visiblePage === item.id
            return (
              <a
                key={item.id}
                href={pageUrlWithContext(item.id as Page)}
                onClick={(event) => onNavigate(event, item.id as Page)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-150 group text-left",
                  isActive
                    ? "bg-navy-light border-l-4 border-gold text-white"
                    : "text-white/80 hover:text-white hover:bg-navy-light/50 border-l-4 border-transparent",
                )}
              >
                <Icon
                  className={cn(
                    "w-5 h-5 flex-shrink-0",
                    isActive
                      ? "text-gold"
                      : "text-teal-light group-hover:text-teal-light",
                  )}
                />
                <span className="font-medium whitespace-nowrap">
                  {item.label}
                </span>
              </a>
            )
          })}
        </nav>

        <div className="p-4 border-t border-navy-light/50">
          <div
            className={cn(
              "flex items-center gap-2 p-1.5 rounded-xl transition-all",
              visiblePage === "profile"
                ? "bg-navy-light border border-gold/40 text-white shadow-xs"
                : "hover:bg-navy-light/50 text-teal-light hover:text-white border border-transparent",
            )}
          >
            <a
              href={pageUrlWithContext("profile")}
              onClick={(event) => onNavigate(event, "profile")}
              className="flex items-center gap-3 flex-1 min-w-0 text-left cursor-pointer group p-1 rounded-lg"
              title="Buka Halaman Profil Pengguna"
            >
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 font-heading font-bold text-xs transition-transform group-hover:scale-105",
                  visiblePage === "profile"
                    ? "bg-gold text-navy"
                    : "bg-teal text-navy-dark",
                )}
              >
                {user?.full_name ? (
                  user.full_name
                    .split(" ")
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((n) => n[0])
                    .join("")
                    .toUpperCase()
                ) : (
                  <User className="w-4 h-4" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate text-white group-hover:text-gold transition-colors">
                  {user?.full_name || "Mahasiswa FTMM"}
                </p>
                <p className="text-xs text-white/70 font-mono truncate">
                  {user?.student_profile?.student_number ||
                    user?.email ||
                    user?.role}
                </p>
              </div>
            </a>

            <button
              type="button"
              onClick={() => onLogoutRequest()}
              title="Keluar / Logout dari Sesi"
              aria-label="Logout"
              className="min-h-11 min-w-11 rounded-lg flex items-center justify-center transition-colors text-white/70 hover:text-orange hover:bg-orange/15 flex-shrink-0 cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}
