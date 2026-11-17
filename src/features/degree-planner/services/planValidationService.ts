import { apiFetch } from "@/shared/api/client"
import type { PlacedCourse } from "@/features/degree-planner/types"

export interface PlanValidationRequest {
  program_studi: string
  semester_saat_ini: number
  riwayat_matkul_lulus: string[]
  maks_sks_per_semester: number
  plan: Record<number, PlacedCourse[]>
}

export interface PlanValidationResult {
  isValid: boolean
  errors: string[]
  warnings: string[]
  totalCredits: number
  semesterCredits: Record<number, number>
}

interface PlanValidationResponseDto {
  is_valid: boolean
  errors: string[]
  warnings: string[]
  total_credits: number
  semester_credits: Record<string, number>
}

const PATH = "/api/v1/plans/validations"

export const planValidationService = {
  validate(
    request: PlanValidationRequest,
    signal?: AbortSignal,
  ): Promise<PlanValidationResult> {
    return apiFetch<PlanValidationResponseDto>(PATH, {
      method: "POST",
      auth: true,
      body: request,
      signal,
    }).then((response) => ({
      isValid: response.is_valid,
      errors: response.errors ?? [],
      warnings: response.warnings ?? [],
      totalCredits: response.total_credits ?? 0,
      semesterCredits: Object.fromEntries(
        Object.entries(response.semester_credits ?? {}).map(
          ([semester, credits]) => [Number(semester), credits],
        ),
      ),
    }))
  },
}
