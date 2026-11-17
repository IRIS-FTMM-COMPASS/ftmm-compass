import { apiFetch } from "@/shared/api/client"
import type { ClassSection, ClassScheduleSlot } from "@/shared/domain/models"
import type {
  ScheduleConflictDetail,
  ScheduleValidationResult,
  SectionAlternative,
} from "@/shared/domain/timetable"

export interface ClassSectionScheduleDto {
  day_of_week: number
  day: string
  start_time: string
  end_time: string
  room: string | null
}

export interface ClassSectionDto {
  section_id: string
  section_code: string
  component_code: string
  component_type: string
  capacity: number | null
  enrollment_status: string
  schedules: ClassSectionScheduleDto[]
}

interface ClassSectionListDto {
  data: ClassSectionDto[]
  meta: { total: number }
}

interface SectionConflictDto {
  course_a_code: string
  course_a_name: string
  section_a_id: string
  section_a_code: string
  course_b_code: string
  course_b_name: string
  section_b_id: string
  section_b_code: string
  day: string
  start_time: string
  end_time: string
}

interface SectionAlternativeDto {
  course_code: string
  course_name: string
  replaces_section_id: string
  section: ClassSectionDto
}

interface ScheduleValidationDto {
  data: SectionConflictDto[]
  alternatives: SectionAlternativeDto[]
  meta: {
    total_conflicts: number
    total_alternatives: number
  }
}

export interface SectionSelectionInput {
  courseCode: string
  sectionId: string
}

const PATH = "/api/v1/class-sections"

function toHours(clock: string): number {
  const [hour, minute] = clock.split(":").map(Number)
  return hour + minute / 60
}

export function mapClassSection(dto: ClassSectionDto): ClassSection {
  const schedules: ClassScheduleSlot[] = dto.schedules.map((meeting) => {
    const start = toHours(meeting.start_time)
    const end = toHours(meeting.end_time)
    return {
      day: meeting.day as ClassScheduleSlot["day"],
      dayOfWeek: meeting.day_of_week,
      start,
      end,
      duration: Math.round((end - start) * 60),
      room: meeting.room || "Ruang belum ditentukan",
    }
  })

  return {
    sectionId: dto.section_id,
    sectionCode: dto.section_code,
    capacity: dto.capacity,
    schedules,
  }
}

export const classSectionService = {
  list(courseCode: string, signal?: AbortSignal): Promise<ClassSectionDto[]> {
    const params = new URLSearchParams({ course_code: courseCode })
    return apiFetch<ClassSectionListDto>(`${PATH}?${params.toString()}`, {
      auth: true,
      signal,
    }).then((response) => response.data)
  },

  validate(
    selections: SectionSelectionInput[],
    signal?: AbortSignal,
  ): Promise<ScheduleValidationResult> {
    return apiFetch<ScheduleValidationDto>(`${PATH}/validations`, {
      method: "POST",
      auth: true,
      body: {
        selections: selections.map((selection) => ({
          course_code: selection.courseCode,
          section_id: selection.sectionId,
        })),
      },
      signal,
    }).then((response) => ({
      conflicts: response.data.map(mapConflict),
      alternatives: response.alternatives.map(mapAlternative),
    }))
  },
}

function mapConflict(dto: SectionConflictDto): ScheduleConflictDetail {
  return {
    courseACode: dto.course_a_code,
    courseAName: dto.course_a_name,
    sectionAId: dto.section_a_id,
    sectionACode: dto.section_a_code,
    courseBCode: dto.course_b_code,
    courseBName: dto.course_b_name,
    sectionBId: dto.section_b_id,
    sectionBCode: dto.section_b_code,
    day: dto.day,
    start: dto.start_time,
    end: dto.end_time,
  }
}

function mapAlternative(dto: SectionAlternativeDto): SectionAlternative {
  return {
    courseCode: dto.course_code,
    courseName: dto.course_name,
    replacesSectionId: dto.replaces_section_id,
    section: mapClassSection(dto.section),
  }
}
