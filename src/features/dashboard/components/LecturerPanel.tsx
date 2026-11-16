import { BookOpen } from "lucide-react"
import type { DashboardMeResponse } from "@/features/dashboard/dashboardService"

interface LecturerPanelProps {
  dashboardData: DashboardMeResponse | null
}

export default function LecturerPanel({ dashboardData }: LecturerPanelProps) {
  return (
    <div className="bg-surface rounded-xl border border-border shadow-sm p-5">
      <div className="flex items-center gap-2.5 border-b border-border/80 pb-3">
        <div className="p-2 rounded-lg bg-navy/10 text-navy">
          <BookOpen className="w-4 h-4" />
        </div>
        <div>
          <h3 className="font-heading font-bold text-base text-navy">
            Kelas Ampuan & Perwalian
          </h3>
          <p className="text-xs text-muted">
            {dashboardData?.stats?.type === "lecturer"
              ? dashboardData.stats.status
              : ""}
          </p>
        </div>
      </div>
      <p className="text-xs text-muted mt-4">
        Belum ada data penugasan mengajar atau perwalian yang tersimpan pada
        periode ini.
      </p>
    </div>
  )
}
