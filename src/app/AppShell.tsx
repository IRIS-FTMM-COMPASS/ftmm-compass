import {
  BookOpen,
  CalendarDays,
  LayoutDashboard,
  LogOut,
  Map,
  MessageSquare,
  Search,
  Users,
} from "lucide-react"
import {
  useRef,
  useState,
  useMemo,
  useEffect,
  useCallback,
  type MouseEvent,
} from "react"
import { cn } from "@/shared/utils"
import type { Course } from "@/shared/domain/models"
import Dashboard from "@/features/dashboard/DashboardPage"
import PjCoursesPage from "@/features/pj/PjCoursesPage"
import CourseFinder from "@/features/course-finder/CourseFinderPage"
import DegreePlanner from "@/features/degree-planner/DegreePlannerPage"
import SchedulingPage from "@/features/scheduling/SchedulingPage"
import PreferencePanel from "@/features/scheduling/components/PreferencePanel"
import InstructorMappingPanel from "@/features/scheduling/components/InstructorMappingPanel"
import AssignmentPanel from "@/features/scheduling/components/AssignmentPanel"
import Chatbot from "@/features/chatbot/ChatbotPage"
import type { DegreePlanPayload } from "@/shared/domain/plan"
import {
  INITIAL_CHAT_MESSAGES,
  INITIAL_STUDENT_PROFILE,
  type ChatMessage,
  type StudentProfileState,
} from "@/features/chatbot/chatService"
import Profile from "@/features/profile/ProfilePage"
import Login from "@/features/auth/LoginPage"
import AdminAccountsPage from "@/features/admin/AdminAccountsPage"
import ConfirmDialog from "@/shared/ui/ConfirmDialog"
import ErrorBoundary from "@/app/components/ErrorBoundary"
import AppSidebar from "@/app/components/AppSidebar"
import AppHeader from "@/app/components/AppHeader"
import { useSession } from "@/features/auth/session"
import { useCatalog } from "@/features/catalog/catalog"
import { usePlanner } from "@/features/degree-planner/state/planner"
import { useAcademicPeriod } from "@/shared/academic-period/academic"
import {
  isPage,
  pageFromLocation,
  pageUrlWithContext,
  pageTitle,
  pathSegment,
  type Page,
} from "@/app/routes"

export default function AppShell() {
  const { user, isLoggedIn, login, logout, canAccess } = useSession()
  const { period } = useAcademicPeriod()
  const { error: catalogError, reload: reloadCatalog } = useCatalog()
  useEffect(() => {
    if (user?.user_id) void reloadCatalog()
  }, [user?.user_id, reloadCatalog])
  const planner = usePlanner()
  const [activePage, setActivePage] = useState<Page>(pageFromLocation)
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return true
    if (window.innerWidth < 1024) return false
    try {
      const stored = window.localStorage.getItem("ftmm:sidebar-open")
      if (stored === "true" || stored === "false") return stored === "true"
    } catch {
      // localStorage dapat tidak tersedia; gunakan lebar layar sebagai cadangan
    }
    return true
  })
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 1024) return
    try {
      window.localStorage.setItem("ftmm:sidebar-open", String(isSidebarOpen))
    } catch {
      // localStorage dapat tidak tersedia; abaikan kegagalan penyimpanan
    }
  }, [isSidebarOpen])
  const [isLogoutModalOpen, setIsLogoutModalOpen] = useState(false)
  const [plannerInitialTab, setPlannerInitialTab] =
    useState<"roadmap" | "timetable">("roadmap")
  const [finderInitialCourse, setFinderInitialCourse] = useState<Course | null>(
    null,
  )
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(
    INITIAL_CHAT_MESSAGES,
  )
  const [chatProfile, setChatProfile] = useState<StudentProfileState>(
    INITIAL_STUDENT_PROFILE,
  )
  const [chatAppliedPlanId, setChatAppliedPlanId] = useState<string | null>(
    null,
  )

  const [teachingTeamView, setTeachingTeamView] = useState({
    page: 1,
    courseFilter: "all",
  })
  const [classAssignmentView, setClassAssignmentView] = useState({
    page: 1,
    contextFilter: "",
  })
  const hasBeenLoggedIn = useRef(isLoggedIn)

  const navigate = useCallback((page: Page, replace = false) => {
    const url = pageUrlWithContext(page)
    if (replace) {
      window.history.replaceState(null, "", url)
    } else {
      window.history.pushState(null, "", url)
    }
    setActivePage(page)
  }, [])
  const openSchedulingPanel = useCallback(
    (
      target: "teaching-team" | "class-assignment",
      params: {
        period?: string | null
        course?: string | null
        reference?: string | null
      },
    ) => {
      const query = new URLSearchParams()
      if (params.period) query.set("period", params.period)
      if (params.course) query.set("course", params.course)
      if (params.reference) query.set("reference", params.reference)
      const search = query.toString()
      window.history.pushState(
        null,
        "",
        `/${target}${search ? `?${search}` : ""}`,
      )
      setTeachingTeamView((view) => ({ ...view, page: 1 }))
      setClassAssignmentView((view) => ({ ...view, page: 1 }))
      setActivePage(target)
    },
    [],
  )

  useEffect(() => {
    const syncFromLocation = () => {
      const pathname = pathSegment()
      const page = pageFromLocation()
      if (pathname !== "" && !isPage(pathname)) {
        window.history.replaceState(null, "", pageUrlWithContext("dashboard"))
      }
      setActivePage(page)
    }
    syncFromLocation()
    window.addEventListener("popstate", syncFromLocation)
    return () => window.removeEventListener("popstate", syncFromLocation)
  }, [])
  useEffect(() => {
    if (isLoggedIn && !canAccess(activePage)) navigate("dashboard", true)
  }, [activePage, canAccess, isLoggedIn, navigate])
  useEffect(() => {
    if (isLoggedIn) {
      hasBeenLoggedIn.current = true
      return
    }
    if (!hasBeenLoggedIn.current) return
    hasBeenLoggedIn.current = false
    setChatMessages(INITIAL_CHAT_MESSAGES)
    setChatProfile(INITIAL_STUDENT_PROFILE)
    setChatAppliedPlanId(null)
    setIsLogoutModalOpen(false)
    navigate("dashboard", true)
  }, [isLoggedIn, navigate])
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return
      if (isLogoutModalOpen) setIsLogoutModalOpen(false)
      else if (isSidebarOpen) setIsSidebarOpen(false)
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isLogoutModalOpen, isSidebarOpen])

  const handleNavigate = (
    page: string,
    options?: {
      tab?: "roadmap" | "timetable"
      course?: Course
    },
  ) => {
    const validPage = isPage(page) ? page : "dashboard"
    setPlannerInitialTab(options?.tab || "roadmap")
    setFinderInitialCourse(options?.course || null)
    navigate(validPage)
  }

  const handleAnchorNavigate = (
    event: MouseEvent<HTMLAnchorElement>,
    page: Page,
  ) => {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }
    event.preventDefault()
    handleNavigate(page)
    if (window.innerWidth < 1024) setIsSidebarOpen(false)
  }

  const canManageSchedule = canAccess("teaching-team")
  const panelParams = new URLSearchParams(window.location.search)
  const visiblePage = canAccess(activePage) ? activePage : "dashboard"

  const handleApplyPlanFromChatbot = (payload: DegreePlanPayload) => {
    planner.applyPlan(payload)
    handleNavigate("degree-planner")
  }

  const handleLogout = () => {
    logout()
    setIsLogoutModalOpen(false)
  }

  const addedCourseIds = new Set(
    planner.pendingCourses.map((course) => course.id),
  )

  const navItems = useMemo(() => {
    const role = user?.role || "student"
    if (role === "lecturer") {
      return [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "preferences", label: "Preferensi Jadwal", icon: CalendarDays },
        { id: "pj-courses", label: "Rekap & Kelola MK", icon: BookOpen },
        { id: "scheduling", label: "Jadwal Bersama", icon: CalendarDays },
        ...(canManageSchedule
          ? [
              { id: "teaching-team", label: "Tim Pengajar", icon: Users },
              {
                id: "class-assignment",
                label: "Penugasan Kelas",
                icon: CalendarDays,
              },
            ]
          : []),
      ] as const
    }

    if (role === "admin") {
      return [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "course-finder", label: "Course Management", icon: BookOpen },
        { id: "admin-accounts", label: "Manajemen Akun", icon: Users },
        { id: "scheduling", label: "Jadwal Bersama", icon: CalendarDays },
        { id: "teaching-team", label: "Tim Pengajar", icon: Users },
        {
          id: "class-assignment",
          label: "Penugasan Kelas",
          icon: CalendarDays,
        },
      ] as const
    }
    if (role !== "student") {
      return [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "course-finder", label: "Course Finder", icon: Search },
      ] as const
    }
    return [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { id: "course-finder", label: "Course Finder", icon: Search },
      { id: "degree-planner", label: "Degree Planner", icon: Map },
      { id: "chatbot", label: "Compass AI", icon: MessageSquare },
    ] as const
  }, [user?.role, user?.is_program_coordinator, canManageSchedule])

  if (!isLoggedIn) {
    return (
      <Login
        onLogin={(next, expiresInSeconds) => {
          login(next, expiresInSeconds)
          navigate("dashboard", true)
        }}
      />
    )
  }

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden font-sans text-foreground">
      <AppSidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        navItems={navItems}
        visiblePage={visiblePage}
        user={user}
        onNavigate={handleAnchorNavigate}
        onLogoutRequest={() => setIsLogoutModalOpen(true)}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {isSidebarOpen && (
          <div
            className="absolute inset-0 bg-black/50 z-10 lg:hidden backdrop-blur-sm"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        <AppHeader
          isOpen={isSidebarOpen}
          onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
          title={pageTitle(visiblePage, user?.role)}
          user={user}
          period={period}
        />

        <div
          className={cn(
            "flex-1 overflow-auto relative",
            visiblePage === "degree-planner"
              ? "p-4 md:px-6 md:py-4"
              : "p-4 md:p-8",
          )}
        >
          {catalogError && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-orange/30 bg-orange/10 px-4 py-3 text-xs text-navy">
              <span>{catalogError}</span>
              <button
                type="button"
                onClick={() => void reloadCatalog()}
                className="min-h-11 rounded-lg border border-orange/40 px-3 font-semibold text-orange transition-colors hover:bg-orange/10 cursor-pointer"
              >
                Coba lagi
              </button>
            </div>
          )}
          <div className="h-full w-full">
            <ErrorBoundary key={visiblePage}>
              {visiblePage === "dashboard" && (
                <Dashboard onNavigate={handleNavigate} />
              )}
              {visiblePage === "course-finder" && (
                <CourseFinder
                  onAddToPlanner={planner.addPendingCourse}
                  addedCourseIds={addedCourseIds}
                  initialCourse={finderInitialCourse}
                  onClearInitialCourse={() => setFinderInitialCourse(null)}
                />
              )}
              {visiblePage === "pj-courses" && user?.role === "lecturer" && (
                <PjCoursesPage onNavigate={handleNavigate} />
              )}
              {visiblePage === "scheduling" &&
                (user?.role === "admin" || user?.role === "lecturer") && (
                  <SchedulingPage onOpenPanel={openSchedulingPanel} />
                )}
              {visiblePage === "teaching-team" && canManageSchedule && (
                <InstructorMappingPanel
                  initialAcademicPeriodId={panelParams.get("period")}
                  initialCurriculumCourseId={panelParams.get("course")}
                  initialReferenceId={panelParams.get("reference")}
                  page={teachingTeamView.page}
                  onPageChange={(nextPage) =>
                    setTeachingTeamView((view) => ({ ...view, page: nextPage }))
                  }
                  courseFilter={teachingTeamView.courseFilter}
                  onCourseFilterChange={(courseFilter) =>
                    setTeachingTeamView((view) => ({
                      ...view,
                      page: 1,
                      courseFilter,
                    }))
                  }
                  onContinueToAssignment={({
                    academicPeriodId,
                    curriculumCourseId,
                  }) =>
                    openSchedulingPanel("class-assignment", {
                      period: academicPeriodId,
                      course: curriculumCourseId,
                    })
                  }
                />
              )}
              {visiblePage === "class-assignment" && canManageSchedule && (
                <AssignmentPanel
                  initialAcademicPeriodId={panelParams.get("period")}
                  initialCurriculumCourseId={panelParams.get("course")}
                  page={classAssignmentView.page}
                  onPageChange={(nextPage) =>
                    setClassAssignmentView((view) => ({
                      ...view,
                      page: nextPage,
                    }))
                  }
                  contextFilter={classAssignmentView.contextFilter}
                  onContextFilterChange={(contextFilter) =>
                    setClassAssignmentView((view) => ({
                      ...view,
                      page: 1,
                      contextFilter,
                    }))
                  }
                />
              )}
              {visiblePage === "preferences" && user?.role === "lecturer" && (
                <PreferencePanel />
              )}
              {visiblePage === "degree-planner" && (
                <DegreePlanner
                  onNavigate={handleNavigate}
                  initialTab={plannerInitialTab}
                />
              )}
              {visiblePage === "chatbot" && (
                <Chatbot
                  messages={chatMessages}
                  onMessagesChange={setChatMessages}
                  profile={chatProfile}
                  onProfileChange={setChatProfile}
                  appliedPlanId={chatAppliedPlanId}
                  onAppliedPlanIdChange={setChatAppliedPlanId}
                  onResetChat={() => {
                    setChatMessages(INITIAL_CHAT_MESSAGES)
                    setChatProfile(INITIAL_STUDENT_PROFILE)
                    setChatAppliedPlanId(null)
                  }}
                  onApplyPlan={handleApplyPlanFromChatbot}
                />
              )}
              {visiblePage === "profile" && (
                <Profile
                  onNavigate={handleNavigate}
                  onRequestLogout={() => setIsLogoutModalOpen(true)}
                />
              )}
              {visiblePage === "admin-accounts" && user?.role === "admin" && (
                <AdminAccountsPage />
              )}
            </ErrorBoundary>
          </div>
        </div>
      </main>

      {isLogoutModalOpen && (
        <ConfirmDialog
          labelledBy="logout-dialog-title"
          title="Konfirmasi Keluar"
          body={
            <p className="text-xs text-muted leading-relaxed">
              Apakah Anda yakin ingin mengakhiri sesi akademik di FTMM Compass?
              Anda dapat masuk kembali kapan saja dengan akun FTMM.
            </p>
          }
          cancelLabel="Batal"
          confirmLabel="Ya, Keluar"
          tone="orange"
          icon={
            <div className="w-12 h-12 rounded-full bg-orange/10 text-orange flex items-center justify-center mx-auto border border-orange/20">
              <LogOut className="w-6 h-6" />
            </div>
          }
          panelClassName="bg-surface rounded-2xl border border-border shadow-2xl max-w-sm w-full p-6 space-y-4 animate-in zoom-in-95 duration-200"
          overlayClassName="bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
          onConfirm={handleLogout}
          onCancel={() => setIsLogoutModalOpen(false)}
        />
      )}
    </div>
  )
}
