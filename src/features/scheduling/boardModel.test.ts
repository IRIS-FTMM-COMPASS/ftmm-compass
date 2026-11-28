import { describe, expect, it } from "vitest"
import type { AuthUser } from "@/features/auth/authService"
import type {
  BoardClassItem,
  BoardConflictItem,
  BoardResponse,
} from "./schedulingService"
import { buildSchedulingModel } from "./boardModel"

function classItem(overrides: Partial<BoardClassItem> = {}): BoardClassItem {
  return {
    class_section_id: "section-1",
    section_code: "A",
    course_code: "TSD101",
    course_name: "Dasar Pemrograman",
    credits: 3,
    face_to_face_minutes: 150,
    course_id: "course-1",
    study_program_id: "tsd",
    study_program_code: "TSD",
    study_program_name: "Teknologi Sains Data",
    programs: [
      {
        study_program_id: "tsd",
        study_program_code: "TSD",
        study_program_name: "Teknologi Sains Data",
        state: "draft",
        label: "Draft",
      },
    ],
    day_of_week: 1,
    start_hour: 7,
    end_hour: 10,
    room_id: "room-1",
    room_code: "A101",
    lecturers: ["Dosen Satu"],
    assigned_lecturer_id: "lecturer-1",
    assigned_lecturer_name: "Dosen Satu",
    assigned_curriculum_course_id: null,
    is_manually_edited: false,
    state: "draft",
    can_edit: true,
    read_only: false,
    is_stale: false,
    run_id: "run-1",
    input_revision: 3,
    ...overrides,
  }
}

function conflict(
  a: string,
  b: string,
  overrides: Partial<BoardConflictItem> = {},
): BoardConflictItem {
  return {
    class_section_a_id: a,
    class_section_b_id: b,
    kind: "room",
    object_id: "room-1",
    object_name: "A101",
    object_label: "Ruang A101",
    class_section_a_label: "TSD101 A",
    class_section_b_label: "TI101 A",
    day_name: "Senin",
    label: "Bentrok ruang A101",
    day_of_week: 1,
    start_hour: 7,
    end_hour: 10,
    ...overrides,
  }
}

function board(classes: BoardClassItem[]): BoardResponse {
  return {
    data: {
      academic_period_id: "period-1",
      period_label: "Ganjil 2026/2027",
      classes,
      conflicts: [conflict("section-1", "section-2")],
      programs: [
        {
          study_program_id: "tsd",
          study_program_code: "TSD",
          study_program_name: "Teknologi Sains Data",
          state: "draft",
          label: "Draft",
          finalized_at: null,
          is_stale: false,
          run_id: "run-1",
          input_revision: 3,
        },
      ],
      unassigned: [
        {
          class_section_id: "section-3",
          course_id: "course-3",
          course_code: "TSD301",
          course_name: "Statistika",
          section_code: "A",
          reason: "Belum ada ruangan",
          reason_code: "no_room",
          programs: [
            {
              study_program_id: "tsd",
              study_program_code: "TSD",
              study_program_name: "Teknologi Sains Data",
            },
          ],
          eligible_curriculum_contexts: [],
          action: "open_room_detail",
          pjmk_reference_id: null,
        },
      ],
    },
    meta: {
      input_revision: 3,
      stale_count: 0,
      actor_study_program_id: "tsd",
      unmapped_room_count: 2,
      unmapped_lecturer_count: 1,
      empty_section_count: 0,
    },
  }
}

const pj: AuthUser = {
  user_id: "lecturer-1",
  email: "pj.tsd@ftmm.unair.ac.id",
  full_name: "PJ TSD",
  role: "lecturer",
  is_program_coordinator: true,
}

describe("buildSchedulingModel", () => {
  it("mengunci cakupan PJ Prodi ke program studinya", () => {
    const model = buildSchedulingModel({
      board: board([classItem(), classItem({ class_section_id: "section-2" })]),
      user: pj,
      selectedProgramId: "ti",
      classScope: "all",
      isFinal: false,
    })

    expect(model.effectiveProgramId).toBe("tsd")
    expect(model.scopedClasses).toHaveLength(2)
    expect(model.finalizeBlockers).toContain("1 kelas belum terjadwal")
    expect(model.actionScopeLabel).toBe("TSD Teknologi Sains Data")
  })

  it("menyembunyikan bentrok di luar cakupan program", () => {
    const model = buildSchedulingModel({
      board: board([classItem(), classItem({ class_section_id: "section-2" })]),
      user: { ...pj, is_program_coordinator: false },
      selectedProgramId: "ti",
      classScope: "all",
      isFinal: false,
    })

    expect(model.visibleConflictRows).toHaveLength(0)
    expect(model.scopedClasses).toHaveLength(0)
    expect(model.canOperateSchedule).toBe(false)
    expect(model.canGenerate).toBe(false)
  })
})
