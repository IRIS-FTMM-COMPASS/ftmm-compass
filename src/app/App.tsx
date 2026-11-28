import { SessionProvider } from "@/features/auth/session"
import { CatalogProvider } from "@/features/catalog/catalog"
import { PollingProvider } from "@/features/polling/polling"
import { PlannerProvider } from "@/features/degree-planner/state/planner"
import { AcademicPeriodProvider } from "@/shared/academic-period/academic"
import AppShell from "@/app/AppShell"

export default function App() {
  return (
    <SessionProvider>
      <AcademicPeriodProvider>
        <CatalogProvider>
          <PollingProvider>
            <PlannerProvider>
              <AppShell />
            </PlannerProvider>
          </PollingProvider>
        </CatalogProvider>
      </AcademicPeriodProvider>
    </SessionProvider>
  )
}
