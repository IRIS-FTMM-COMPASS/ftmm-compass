import { useMemo, useState } from "react"
import { getProdiAbbreviation } from "@/shared/domain/course"
import type { Course } from "@/shared/domain/models"
import type { PollingPeriod } from "@/features/polling/pollingService"

type CourseTypeFilter = "all" | "Wajib" | "Pilihan"
type AvailabilityFilter = "all" | "open" | "closed"
type ParityFilter = "all" | "odd" | "even"

interface UseCourseFiltersArgs {
  catalogCourses: Course[]
  programs: string[]
  demandStats: Record<string, number>
  pollingPeriod: PollingPeriod | null
}

export interface CourseFiltersReturn {
  activeProgram: string
  setActiveProgram: (value: string) => void
  availablePrograms: string[]
  courses: Course[]
  creditCounts: Record<string, number>
  searchQuery: string
  setSearchQuery: (value: string) => void
  selectedType: CourseTypeFilter
  setSelectedType: (value: CourseTypeFilter) => void
  selectedAvailability: AvailabilityFilter
  setSelectedAvailability: (value: AvailabilityFilter) => void
  selectedParity: ParityFilter
  setSelectedParity: (value: ParityFilter) => void
  selectedCredits: string
  setSelectedCredits: (value: string) => void
  selectedCategory: string
  setSelectedCategory: (value: string) => void
  filterMostDemanded: boolean
  setFilterMostDemanded: (value: boolean) => void
  filtered: Course[]
  rankedCourseCodes: Record<string, number>
  hasActiveFilters: boolean
  handleResetFilters: () => void
}

export function useCourseFilters({
  catalogCourses,
  programs,
  demandStats,
  pollingPeriod,
}: UseCourseFiltersArgs) {
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedType, setSelectedType] = useState<CourseTypeFilter>("all")
  const [selectedAvailability, setSelectedAvailability] =
    useState<AvailabilityFilter>("all")
  const [selectedParity, setSelectedParity] = useState<ParityFilter>("all")
  const [selectedCredits, setSelectedCredits] = useState<string>("all")
  const [selectedCategory, setSelectedCategory] = useState<string>("all")
  const [filterMostDemanded, setFilterMostDemanded] = useState(false)
  const [activeProgram, setActiveProgram] = useState<string>("all")

  const courses = useMemo(
    () =>
      activeProgram === "all"
        ? catalogCourses
        : catalogCourses.filter((course) => course.program === activeProgram),
    [activeProgram, catalogCourses],
  )

  const availablePrograms = programs

  const creditCounts = useMemo(() => {
    const counts: Record<string, number> = { other: 0 }
    for (const item of courses) {
      const key =
        item.credits >= 1 && item.credits <= 4 ? String(item.credits) : "other"
      counts[key] = (counts[key] ?? 0) + 1
    }
    return counts
  }, [courses])

  const voteKey = (course: Course) => course.code || course.id
  const votesFor = (course: Course) => demandStats[voteKey(course)] ?? 0

  const rankedCourseCodes = useMemo(() => {
    const list = courses
      .map((c) => ({
        key: c.code || c.id,
        votes: votesFor(c),
      }))
      .filter((it) => it.votes > 0)
      .sort((a, b) => b.votes - a.votes)
    const map: Record<string, number> = {}
    list.forEach((it, idx) => {
      map[it.key] = idx + 1
    })
    return map
  }, [courses, demandStats])

  const filtered = useMemo(() => {
    const minQ = pollingPeriod?.min_quorum ?? 0
    const list = courses.filter((c) => {
      const q = searchQuery.toLowerCase().trim()
      const matchesSearch =
        !q ||
        c.name.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q) ||
        (c.code ?? "").toLowerCase().includes(q) ||
        (c.prodiAbbr ?? "").toLowerCase().includes(q) ||
        (c.program ?? "").toLowerCase().includes(q)

      const matchesProgram =
        activeProgram === "all" ||
        c.program === activeProgram ||
        Boolean(
          c.prodiAbbr && getProdiAbbreviation(activeProgram) === c.prodiAbbr,
        )

      const matchesType = selectedType === "all" || c.type === selectedType

      const votes = votesFor(c)
      const isCourseOpen = c.type === "Wajib" || votes >= minQ

      const matchesAvailability =
        selectedAvailability === "all" ||
        (selectedAvailability === "open" && isCourseOpen) ||
        (selectedAvailability === "closed" && !isCourseOpen)

      const matchesParity =
        selectedParity === "all" || c.parity === selectedParity

      const matchesCredits =
        selectedCredits === "all" ||
        (selectedCredits === "2" && c.credits === 2) ||
        (selectedCredits === "3" && c.credits === 3) ||
        (selectedCredits === "4" && c.credits === 4) ||
        (selectedCredits === "1" && c.credits === 1) ||
        (selectedCredits === "other" && c.credits > 4)

      const matchesCategory =
        selectedCategory === "all" || c.category === selectedCategory

      return (
        matchesSearch &&
        matchesProgram &&
        matchesType &&
        matchesAvailability &&
        matchesParity &&
        matchesCredits &&
        matchesCategory
      )
    })

    if (filterMostDemanded) {
      const withVotes = list.filter((c) => votesFor(c) > 0)
      const targetList = withVotes.length > 0 ? withVotes : list
      return [...targetList].sort((a, b) => {
        const aVotes = votesFor(a)
        const bVotes = votesFor(b)
        return bVotes - aVotes
      })
    }

    return list
  }, [
    courses,
    searchQuery,
    activeProgram,
    selectedType,
    selectedAvailability,
    selectedParity,
    selectedCredits,
    selectedCategory,
    filterMostDemanded,
    demandStats,
    pollingPeriod,
  ])

  const hasActiveFilters =
    searchQuery.trim() !== "" ||
    activeProgram !== "all" ||
    selectedType !== "all" ||
    selectedAvailability !== "all" ||
    selectedParity !== "all" ||
    selectedCredits !== "all" ||
    selectedCategory !== "all" ||
    filterMostDemanded

  const handleResetFilters = () => {
    setSearchQuery("")
    setActiveProgram("all")
    setSelectedType("all")
    setSelectedAvailability("all")
    setSelectedParity("all")
    setSelectedCredits("all")
    setSelectedCategory("all")
    setFilterMostDemanded(false)
  }

  return {
    activeProgram,
    setActiveProgram,
    availablePrograms,
    courses,
    creditCounts,
    searchQuery,
    setSearchQuery,
    selectedType,
    setSelectedType,
    selectedAvailability,
    setSelectedAvailability,
    selectedParity,
    setSelectedParity,
    selectedCredits,
    setSelectedCredits,
    selectedCategory,
    setSelectedCategory,
    filterMostDemanded,
    setFilterMostDemanded,
    filtered,
    hasActiveFilters,
    handleResetFilters,
    rankedCourseCodes,
  }
}
