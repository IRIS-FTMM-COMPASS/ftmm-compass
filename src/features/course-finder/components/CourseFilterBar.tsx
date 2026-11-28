import { useState } from "react"
import {
  CheckCircle2,
  Clock,
  Flame,
  GraduationCap,
  Layers,
  Plus,
  RotateCcw,
  Search,
  SlidersHorizontal,
} from "lucide-react"
import type { AuthUser } from "@/features/auth/authService"
import type { CourseFiltersReturn } from "@/features/course-finder/hooks/useCourseFilters"
import { getProdiAbbreviation } from "@/shared/domain/course"
import { cn } from "@/shared/utils"

interface CourseFilterBarProps {
  filters: CourseFiltersReturn
  currentUser: AuthUser | null
  onCreateCourse: () => void
}

export default function CourseFilterBar({
  filters,
  currentUser,
  onCreateCourse,
}: CourseFilterBarProps) {
  const {
    searchQuery,
    setSearchQuery,
    activeProgram,
    setActiveProgram,
    availablePrograms,
    selectedType,
    setSelectedType,
    selectedAvailability,
    setSelectedAvailability,
    selectedParity,
    setSelectedParity,
    selectedCredits,
    setSelectedCredits,
    creditCounts,
    selectedCategory,
    setSelectedCategory,
    filterMostDemanded,
    setFilterMostDemanded,
    hasActiveFilters,
    handleResetFilters,
    filtered,
    courses,
  } = filters

  const isProdiScoped =
    currentUser?.role === "student" ||
    (currentUser?.role === "lecturer" &&
      currentUser?.is_program_coordinator === true)
  const scopedProdi =
    currentUser?.student_profile?.study_program ??
    currentUser?.unit_name ??
    "Program Studi"
  const [filtersOpen, setFiltersOpen] = useState(false)

  return (
    <div className="sticky top-0 z-20 space-y-3.5 rounded-xl border border-border bg-surface p-4 shadow-sm mb-4 flex-shrink-0">
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted" />
          <input
            type="text"
            placeholder="Cari mata kuliah atau kode"
            className="w-full min-h-11 pl-10 pr-4 rounded-xl border border-border focus:border-gold focus:ring-1 focus:ring-gold outline-hidden transition-all text-sm font-sans"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        {currentUser?.role === "admin" && (
          <button
            type="button"
            onClick={onCreateCourse}
            title="Tambah Mata Kuliah"
            aria-label="Tambah Mata Kuliah"
            className="min-h-11 min-w-11 px-3.5 rounded-xl bg-gold hover:bg-gold/90 text-navy font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all cursor-pointer flex-shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Tambah Mata Kuliah</span>
          </button>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 md:hidden">
        <span className="text-[11px] font-mono font-medium text-muted">
          {filtered.length} dari {courses.length} matkul
        </span>
        <button
          type="button"
          onClick={() => setFiltersOpen((open) => !open)}
          aria-expanded={filtersOpen}
          aria-controls="course-filter-controls"
          className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-border bg-background px-3 text-xs font-semibold text-navy transition-colors hover:border-gold"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          {filtersOpen ? "Tutup Filter" : "Filter"}
        </button>
      </div>

      <div
        id="course-filter-controls"
        className={cn(
          "space-y-3.5",
          filtersOpen
            ? "max-h-[60vh] overflow-y-auto pr-1 md:max-h-none md:overflow-visible"
            : "hidden md:block",
        )}
      >
        {isProdiScoped && (
          <div className="inline-flex min-h-11 w-fit items-center gap-2 rounded-lg border border-border bg-background px-3 text-xs font-medium text-navy">
            <Layers className="w-3.5 h-3.5 text-muted" />
            <span>{scopedProdi}</span>
          </div>
        )}
        {!isProdiScoped && (
          <div className="flex flex-wrap items-center gap-2 md:flex-nowrap md:overflow-x-auto md:pb-1 md:scrollbar-none">
            <button
              type="button"
              onClick={() => setActiveProgram("all")}
              aria-pressed={activeProgram === "all"}
              className={cn(
                "min-h-11 min-w-11 px-3 rounded-lg text-xs font-medium whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 flex-shrink-0",
                activeProgram === "all"
                  ? "bg-gold text-navy shadow-xs font-semibold"
                  : "bg-surface border border-border text-muted hover:text-navy hover:bg-navy/5",
              )}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Semua Program</span>
            </button>
            {availablePrograms.map((p) => {
              const abbr = getProdiAbbreviation(p)
              const isActive = activeProgram === p
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setActiveProgram(p)}
                  title={p}
                  aria-pressed={isActive}
                  className={cn(
                    "min-h-11 min-w-11 px-3 rounded-lg text-xs whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 flex-shrink-0",
                    isActive
                      ? "bg-navy text-white shadow-xs font-bold"
                      : "bg-surface border border-border text-muted hover:text-navy hover:bg-navy/5",
                  )}
                >
                  <span className="font-mono font-bold">{abbr}</span>
                  <span className="hidden sm:inline font-normal text-[11px] opacity-80">
                    &bull; {p}
                  </span>
                </button>
              )
            })}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/50 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg border border-border bg-background p-0.5">
              <button
                type="button"
                onClick={() => setSelectedType("all")}
                aria-pressed={selectedType === "all"}
                className={cn(
                  "min-h-11 min-w-11 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  selectedType === "all"
                    ? "bg-navy text-white font-semibold"
                    : "text-muted hover:text-navy",
                )}
              >
                Semua Tipe
              </button>
              <button
                type="button"
                onClick={() => setSelectedType("Wajib")}
                aria-pressed={selectedType === "Wajib"}
                className={cn(
                  "min-h-11 min-w-11 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  selectedType === "Wajib"
                    ? "bg-navy text-white font-semibold"
                    : "text-muted hover:text-navy",
                )}
              >
                Wajib
              </button>
              <button
                type="button"
                onClick={() => setSelectedType("Pilihan")}
                aria-pressed={selectedType === "Pilihan"}
                className={cn(
                  "min-h-11 min-w-11 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  selectedType === "Pilihan"
                    ? "bg-gold text-navy font-bold shadow-xs"
                    : "text-muted hover:text-navy",
                )}
              >
                Pilihan
              </button>
            </div>

            <div className="inline-flex rounded-lg border border-border bg-background p-0.5">
              <button
                type="button"
                onClick={() => setSelectedParity("all")}
                aria-pressed={selectedParity === "all"}
                className={cn(
                  "min-h-11 min-w-11 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  selectedParity === "all"
                    ? "bg-navy text-white"
                    : "text-muted hover:text-navy",
                )}
              >
                Semua Sem
              </button>
              <button
                type="button"
                onClick={() => setSelectedParity("odd")}
                aria-pressed={selectedParity === "odd"}
                className={cn(
                  "min-h-11 min-w-11 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  selectedParity === "odd"
                    ? "bg-navy text-white"
                    : "text-muted hover:text-navy",
                )}
              >
                Ganjil
              </button>
              <button
                type="button"
                onClick={() => setSelectedParity("even")}
                aria-pressed={selectedParity === "even"}
                className={cn(
                  "min-h-11 min-w-11 px-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                  selectedParity === "even"
                    ? "bg-navy text-white"
                    : "text-muted hover:text-navy",
                )}
              >
                Genap
              </button>
            </div>

            <div className="relative">
              <select
                value={selectedCredits}
                onChange={(e) => setSelectedCredits(e.target.value)}
                className="h-11 pl-3 pr-8 rounded-lg border border-border bg-background text-xs font-medium text-foreground hover:border-gold focus:border-gold focus:ring-1 focus:ring-gold outline-hidden cursor-pointer appearance-none transition-colors"
                aria-label="Filter Bobot SKS"
              >
                <option value="all">Bobot SKS: Semua</option>
                <option value="2">2 SKS ({creditCounts["2"] ?? 0} MK)</option>
                <option value="3">3 SKS ({creditCounts["3"] ?? 0} MK)</option>
                <option value="4">4 SKS ({creditCounts["4"] ?? 0} MK)</option>
                <option value="1">
                  1 SKS (Praktikum, {creditCounts["1"] ?? 0})
                </option>
                <option value="other">
                  &gt; 4 SKS (Tugas Akhir, {creditCounts.other})
                </option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-muted">
                <Clock className="w-3.5 h-3.5" />
              </div>
            </div>

            <div className="relative">
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="h-11 pl-3 pr-8 rounded-lg border border-border bg-background text-xs font-medium text-foreground hover:border-gold focus:border-gold focus:ring-1 focus:ring-gold outline-hidden cursor-pointer appearance-none transition-colors"
                aria-label="Filter Kategori PDB"
              >
                <option value="all">Kategori: Semua</option>
                <option value="pdb_univ">PDB Universitas</option>
                <option value="pdb_saintek">PDB Saintek</option>
                <option value="prodi">Mata Kuliah Prodi</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-muted">
                <GraduationCap className="w-3.5 h-3.5" />
              </div>
            </div>

            <div className="relative">
              <select
                value={selectedAvailability}
                onChange={(e) =>
                  setSelectedAvailability(
                    e.target.value as "all" | "open" | "closed",
                  )
                }
                className="h-11 pl-3 pr-8 rounded-lg border border-border bg-background text-xs font-medium text-foreground hover:border-gold focus:border-gold focus:ring-1 focus:ring-gold outline-hidden cursor-pointer appearance-none transition-colors"
                aria-label="Filter Ketersediaan"
              >
                <option value="all">Status Kelas: Semua</option>
                <option value="open">Dibuka Semester Ini</option>
                <option value="closed">Ditutup Semester Ini</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-muted">
                <CheckCircle2 className="w-3.5 h-3.5" />
              </div>
            </div>

            <button
              type="button"
              onClick={() => setFilterMostDemanded(!filterMostDemanded)}
              aria-pressed={filterMostDemanded}
              className={cn(
                "min-h-11 min-w-11 px-2.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer",
                filterMostDemanded
                  ? "bg-orange text-white border-orange shadow-xs"
                  : "bg-surface border-border text-muted hover:text-orange hover:border-orange/50",
              )}
              title="Urutkan mata kuliah berdasarkan peminat terbanyak"
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Paling Diminati</span>
            </button>

            {hasActiveFilters && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="inline-flex items-center gap-1 min-h-11 min-w-11 px-2.5 text-xs font-medium text-muted hover:text-navy hover:bg-navy/5 rounded-lg border border-border/80 transition-colors cursor-pointer"
                title="Reset seluruh filter"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset</span>
              </button>
            )}
          </div>

          <span className="hidden text-[11px] text-muted font-mono font-medium md:inline">
            {filtered.length} dari {courses.length} matkul
          </span>
        </div>
      </div>
    </div>
  )
}
