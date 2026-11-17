import { apiFetch } from "@/shared/api/client"
import type { ClassScheduleSlot, ClassSection } from "@/shared/domain/models"

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
}
