import { describe, expect, it } from "vitest"

import {
  getProdiAbbreviation,
  normalizeCourse,
  normalizeCourseType,
  normalizeProgramName,
} from "@/shared/domain/course"

describe("normalizeCourse", () => {
  it("normalizes program, type, id, and parity from one source", () => {
    const course = normalizeCourse({
      code: " TSD201 ",
      name: "Basis Data",
      credits: 3,
      semester: 3,
      type: "Pilihan",
      program: "S1 Teknologi Sains Data",
    })

    expect(course.id).toBe("teknologi-sains-data:TSD201")
    expect(course.program).toBe("Teknologi Sains Data")
    expect(course.prodiAbbr).toBe("TSD")
    expect(course.type).toBe("Pilihan")
    expect(course.parity).toBe("odd")
  })

  it("suffixes duplicate ids instead of overwriting", () => {
    const used = new Set<string>()
    const first = normalizeCourse(
      {
        code: "TSD201",
        name: "Basis Data",
        credits: 3,
        semester: 3,
        program: "Teknologi Sains Data",
      },
      used,
    )
    const second = normalizeCourse(
      {
        code: "TSD201",
        name: "Basis Data Lanjutan",
        credits: 3,
        semester: 3,
        program: "Teknologi Sains Data",
      },
      used,
    )

    expect(used.has(first.id)).toBe(true)
    expect(second.id).not.toBe(first.id)
  })
})

describe("program normalization", () => {
  it("removes the S1 prefix and resolves abbreviations", () => {
    expect(normalizeProgramName("S1 Rekayasa Nanoteknologi")).toBe(
      "Rekayasa Nanoteknologi",
    )
    expect(getProdiAbbreviation("S1 Rekayasa Nanoteknologi")).toBe("RN")
  })

  it("treats elective wording as Pilihan", () => {
    expect(normalizeCourseType("mata kuliah pilihan")).toBe("Pilihan")
    expect(normalizeCourseType("wajib")).toBe("Wajib")
  })
})
