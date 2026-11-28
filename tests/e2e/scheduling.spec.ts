import { expect, test } from "@playwright/test"
import { STORAGE_STATE, storageToken } from "./support/app"

interface BoardClass {
  class_section_id: string
  course_code: string
  section_code: string
  day_of_week: number
  start_hour: number
  room_id: string | null
  can_edit: boolean
}

test.use({ storageState: STORAGE_STATE.admin })

test.describe("Penjadwalan admin", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/scheduling")
    await expect(
      page.getByRole("heading", { name: "Penjadwalan", exact: true }),
    ).toBeVisible()
  })

  test("memuat papan dan kontrol penjadwalan", async ({ page }) => {
    await expect(page.getByText("Papan Jadwal Bersama")).toBeVisible()
    await expect(page.getByText("Kontrol Penjadwalan")).toBeVisible()
    await expect(page.getByLabel("Filter program studi")).toBeVisible()
    await expect(
      page.getByRole("tab", { name: "Papan Jadwal" }),
    ).toHaveAttribute("aria-selected", "true")
  })

  test("navigasi tab dengan keyboard", async ({ page }) => {
    await page.getByRole("tab", { name: "Papan Jadwal" }).focus()
    await page.keyboard.press("ArrowRight")

    await expect(page.getByRole("tab", { name: "Ruangan" })).toHaveAttribute(
      "aria-selected",
      "true",
    )
    await expect(
      page.getByRole("heading", { name: "Kelola Ruangan" }),
    ).toBeVisible()

    await page.getByRole("tab", { name: "Deadline Preferensi" }).click()
    await expect(
      page.getByRole("heading", {
        name: "Deadline dan Kelengkapan Preferensi",
      }),
    ).toBeVisible()
  })

  test("membuka detail kelas dari papan", async ({ page }) => {
    const card = page
      .getByRole("button", { name: /Tampilkan detail kelas/ })
      .first()
    await expect(card).toBeVisible()
    await card.click()

    await expect(page.getByRole("dialog")).toBeVisible()
    await page.getByRole("button", { name: "Tutup detail kelas" }).click()
    await expect(page.getByRole("dialog")).toHaveCount(0)
  })

  test("menyimpan perubahan jadwal lalu memulihkannya", async ({
    page,
    request,
  }) => {
    const headers = {
      Authorization: `Bearer ${storageToken(STORAGE_STATE.admin)}`,
    }
    const boardResponse = await request.get("/api/v1/scheduling/board", {
      headers,
    })
    expect(boardResponse.ok()).toBeTruthy()
    const board = (await boardResponse.json()) as {
      data: { classes: BoardClass[] }
    }
    const target = board.data.classes.find(
      (item) => item.can_edit && item.room_id,
    )
    if (!target) {
      test.skip(true, "Tidak ada kelas yang dapat diubah pada data seed.")
      return
    }

    const original = {
      day_of_week: target.day_of_week,
      start_hour: target.start_hour,
      room_id: target.room_id,
    }
    const changedDay = original.day_of_week === 5 ? 1 : original.day_of_week + 1
    let submitted = false

    const currentDay = async () => {
      const response = await request.get("/api/v1/scheduling/board", {
        headers,
      })
      const data = (await response.json()) as {
        data: { classes: BoardClass[] }
      }
      return data.data.classes.find(
        (item) => item.class_section_id === target.class_section_id,
      )?.day_of_week
    }

    try {
      const card = page.getByRole("button", {
        name: new RegExp(
          `${target.course_code} .*kelas ${target.section_code}\\. Tampilkan detail kelas`,
        ),
      })
      await expect(card).toBeVisible()
      await card.click()
      await page.getByRole("button", { name: "Ubah jadwal" }).click()

      await page
        .getByRole("combobox", { name: "Hari", exact: true })
        .selectOption(String(changedDay))
      await page
        .getByRole("textbox", { name: /Alasan perubahan/ })
        .fill("Uji E2E perubahan jadwal")
      await page.getByRole("button", { name: "Simpan perubahan" }).click()
      submitted = true

      await expect(page.getByText(/jadwal kelas tersimpan/i)).toBeVisible()
      await expect(
        page.getByRole("heading", { name: /Ubah jadwal/ }),
      ).toHaveCount(0)
      await expect.poll(currentDay).toBe(changedDay)
    } finally {
      // shortcut: audit log tidak dapat dihapus lewat API; baris jadwal dipulihkan penuh.
      if (submitted) {
        const restored = await request.patch(
          `/api/v1/scheduling/classes/${target.class_section_id}`,
          {
            headers,
            data: {
              ...original,
              reason: "Pemulihan data uji E2E",
            },
          },
        )
        expect(restored.ok()).toBeTruthy()
        await expect.poll(currentDay).toBe(original.day_of_week)
      }
    }
  })
})

test.describe("Penjadwalan mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test("navigasi mobile dan papan tidak meluber", async ({ page }) => {
    await page.goto("/scheduling")
    await expect(
      page.getByRole("heading", { name: "Penjadwalan", exact: true }),
    ).toBeVisible()

    await page.getByRole("button", { name: "Buka bilah navigasi" }).click()
    await expect(page.getByRole("button", { name: "Tutup menu" })).toBeVisible()
    await page
      .getByRole("link", { name: "Jadwal Bersama", exact: true })
      .click()

    await expect(page.getByText("Papan Jadwal Bersama")).toBeVisible()

    const overflow = await page.evaluate(() => {
      const root = document.documentElement
      return root.scrollWidth - root.clientWidth
    })
    expect(overflow).toBeLessThanOrEqual(1)
  })
})
