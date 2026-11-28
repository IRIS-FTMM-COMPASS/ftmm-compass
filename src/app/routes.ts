export type Page = "dashboard" | "preferences" | "course-finder" | "pj-courses" | "degree-planner" | "scheduling" | "teaching-team" | "class-assignment" | "chatbot" | "profile" | "admin-accounts"

const PAGES: Page[] = [
  "dashboard",
  "preferences",
  "course-finder",
  "pj-courses",
  "degree-planner",
  "scheduling",
  "teaching-team",
  "class-assignment",
  "chatbot",
  "profile",
  "admin-accounts",
]
export function isPage(value: string): value is Page {
  return PAGES.includes(value as Page)
}

export function pathSegment(): string {
  return window.location.pathname.replace(/^\/+|\/+$/g, "")
}

export function pageFromLocation(): Page {
  const path = pathSegment()
  return isPage(path) ? path : "dashboard"
}

export function pageUrl(page: Page): string {
  return `/${page}`
}

export function pageUrlWithContext(page: Page): string {
  return pageUrl(page) + window.location.search + window.location.hash
}

const PAGE_TITLES: Record<Page, string> = {
  dashboard: "Dashboard",
  preferences: "Preferensi Jadwal",
  "course-finder": "Course Finder",
  "pj-courses": "Rekap & Kelola MK",
  "degree-planner": "Degree Planner",
  scheduling: "Jadwal Bersama",
  "teaching-team": "Tim Pengajar",
  "class-assignment": "Penugasan Kelas",
  chatbot: "Compass AI",
  profile: "Profil Pengguna",
  "admin-accounts": "Manajemen Akun",
}

export function pageTitle(page: Page, role?: string): string {
  if (page === "course-finder" && role === "admin") {
    return "Course Management"
  }
  return PAGE_TITLES[page]
}
