import { describe, expect, it } from "vitest"

import {
  canDrop,
  courseKey,
  isCompleted,
} from "@/features/degree-planner/types"
import type { PlanCourse } from "@/shared/domain/plan"

function course(overrides: Partial<PlanCourse> = {}): PlanCourse {
  return {
    id: "c1",
    code: "TSD201",
    name: "Basis Data",
    credits: 3,
    semester: 3,
    type: "Pilihan",
    parity: "odd",
    desc: "",
    program: "Teknologi Sains Data",
    prerequisites: [],
    status: "planned",
    ...overrides,
  } as PlanCourse
}

describe("planner drop rules", () => {
  it("uses the course code as the stable key", () => {
    expect(courseKey({ id: "id", code: "TSD201" })).toBe("TSD201")
    expect(courseKey({ id: "id" })).toBe("id")
  })

  it("blocks completed and required courses from moving semesters", () => {
    expect(isCompleted(course({ status: "completed" }))).toBe(true)
    expect(canDrop(course({ status: "completed" }), 4, 3)).toBe(false)
    expect(canDrop(course({ type: "Wajib" }), 4, 3)).toBe(false)
  })

  it("enforces parity for electives but allows same-semester moves", () => {
    expect(canDrop(course({ parity: "odd" }), 4, 3)).toBe(false)
    expect(canDrop(course({ parity: "even" }), 4, 3)).toBe(true)
    expect(canDrop(course({ parity: "odd" }), 3, 5)).toBe(true)
  })
})
