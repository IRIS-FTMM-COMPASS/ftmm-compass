import { describe, expect, it } from "vitest"

import { pageTitle } from "@/app/routes"

describe("pageTitle", () => {
  it("uses the admin label for course management", () => {
    expect(pageTitle("course-finder", "admin")).toBe("Course Management")
    expect(pageTitle("course-finder", "student")).toBe("Course Finder")
  })

  it("uses the real label for preferences instead of the route slug", () => {
    expect(pageTitle("preferences")).toBe("Preferensi Jadwal")
  })
})
