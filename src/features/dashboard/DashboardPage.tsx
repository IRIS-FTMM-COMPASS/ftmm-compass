import { useAcademicPeriod } from "@/shared/academic-period/academic"
import { useSession } from "@/features/auth/session"
import DashboardMainPanel from "@/features/dashboard/components/DashboardMainPanel"
import DashboardStats from "@/features/dashboard/components/DashboardStats"
import LecturerDashboard from "@/features/dashboard/components/LecturerDashboard"
import PollingPanel from "@/features/dashboard/components/PollingPanel"
import { useDashboardData } from "@/features/dashboard/hooks/useDashboardData"
import { useDemandAnalytics } from "@/features/dashboard/hooks/useDemandAnalytics"
import { usePolling } from "@/features/polling/polling"

interface DashboardProps {
  onNavigate: (page: string) => void
}

export default function Dashboard({ onNavigate }: DashboardProps) {
  const { user } = useSession()
  const { period } = useAcademicPeriod()
  const {
    period: pollingPeriod,
    myVotes: studentVotes,
    error: pollingError,
  } = usePolling()
  const {
    dashboardData,
    isLoading,
    displayedSchedule,
    hasConflict,
    error,
    retry,
  } = useDashboardData(user)
  const {
    selectedProdi,
    setSelectedProdi,
    demandAnalytics,
    items,
    isLoadingAnalytics,
    handleExportCSV,
  } = useDemandAnalytics(user)

  const adminStats =
    dashboardData?.stats.type === "admin" ? dashboardData.stats : null
  const canViewPollingAnalytics =
    user?.role === "admin" ||
    (user?.role === "lecturer" && user.is_program_coordinator === true)

  if (user?.role === "lecturer") {
    return (
      <div className="space-y-6">
        <LecturerDashboard
          dashboardData={dashboardData}
          isLoading={isLoading}
          error={error}
          retry={retry}
          onNavigate={onNavigate}
        />
        {canViewPollingAnalytics && (
          <PollingPanel
            user={user}
            studentVotes={studentVotes}
            pollingPeriod={pollingPeriod}
            onNavigate={onNavigate}
            selectedProdi={selectedProdi}
            setSelectedProdi={setSelectedProdi}
            items={items}
            demandAnalytics={demandAnalytics}
            isLoadingAnalytics={isLoadingAnalytics}
            handleExportCSV={handleExportCSV}
          />
        )}
      </div>
    )
  }

  if (isLoading && !dashboardData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3 text-muted">
        <div className="w-8 h-8 border-2 border-gold/30 border-t-gold rounded-full animate-spin" />
        <p className="text-xs font-mono">Memuat data dashboard akademik...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {error && (
        <div
          role="alert"
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 rounded-xl border border-orange/30 bg-orange/10 text-sm text-navy"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={retry}
            className="min-h-11 px-4 rounded-lg bg-navy text-white font-medium hover:bg-navy-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
          >
            Coba lagi
          </button>
        </div>
      )}
      <DashboardStats
        dashboardData={dashboardData}
        pollingPeriod={pollingPeriod}
        period={period}
      />
      <DashboardMainPanel
        user={user}
        dashboardData={dashboardData}
        adminStats={adminStats}
        period={period}
        displayedSchedule={displayedSchedule}
        hasConflict={hasConflict}
        onNavigate={onNavigate}
      />
      {(user?.role !== "lecturer" || canViewPollingAnalytics) &&
        pollingError && (
          <div
            role="status"
            className="px-4 py-2.5 rounded-xl border border-orange/30 bg-orange/10 text-xs text-navy"
          >
            {pollingError}
          </div>
        )}
      {(user?.role === "student" || canViewPollingAnalytics) && (
        <PollingPanel
          user={user}
          studentVotes={studentVotes}
          pollingPeriod={pollingPeriod}
          onNavigate={onNavigate}
          selectedProdi={selectedProdi}
          setSelectedProdi={setSelectedProdi}
          items={items}
          demandAnalytics={demandAnalytics}
          isLoadingAnalytics={isLoadingAnalytics}
          handleExportCSV={handleExportCSV}
        />
      )}
    </div>
  )
}
