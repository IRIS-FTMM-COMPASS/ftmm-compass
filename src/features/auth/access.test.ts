import { describe, expect, it } from "vitest"

import { canAccessPage, canManageSchedule } from "@/features/auth/access"
import type { AuthUser } from "@/features/auth/authService"

function user(role: string, coordinator = false): AuthUser {
  return {
    user_id: "u1",
    email: "u@example.test",
    full_name: "Uji",
    role,
    is_program_coordinator: coordinator,
  }
}

describe("canAccessPage", () => {
  it("keeps student pages student-only", () => {
    expect(canAccessPage(user("student"), "degree-planner")).toBe(true)
    expect(canAccessPage(user("student"), "chatbot")).toBe(true)
    expect(canAccessPage(user("student"), "scheduling")).toBe(false)
    expect(canAccessPage(user("student"), "admin-accounts")).toBe(false)
  })

  it("gives lecturers schedule management only as coordinators", () => {
    expect(canAccessPage(user("lecturer"), "scheduling")).toBe(true)
    expect(canAccessPage(user("lecturer"), "preferences")).toBe(true)
    expect(canAccessPage(user("lecturer"), "teaching-team")).toBe(false)
    expect(canAccessPage(user("lecturer", true), "teaching-team")).toBe(true)
  })

  it("gives admins every guarded page", () => {
    for (const page of [
      "admin-accounts",
      "scheduling",
      "teaching-team",
      "class-assignment",
    ]) {
      expect(canAccessPage(user("admin"), page)).toBe(true)
    }
  })

  it("keeps faculty staff out of guarded pages", () => {
    expect(canAccessPage(user("faculty_staff"), "dashboard")).toBe(true)
    expect(canAccessPage(user("faculty_staff"), "scheduling")).toBe(false)
    expect(canAccessPage(user("faculty_staff"), "admin-accounts")).toBe(false)
  })
})

describe("canManageSchedule", () => {
  it("allows admins and lecturer coordinators only", () => {
    expect(canManageSchedule(user("admin"))).toBe(true)
    expect(canManageSchedule(user("lecturer", true))).toBe(true)
    expect(canManageSchedule(user("lecturer"))).toBe(false)
    expect(canManageSchedule(user("student"))).toBe(false)
    expect(canManageSchedule(null)).toBe(false)
  })
})
