import { expect, test } from "@playwright/test"
import { STORAGE_STATE } from "./support/app"

test.use({ storageState: STORAGE_STATE.student })

test.describe("Course Finder", () => {
  test("mencari mata kuliah dari katalog backend", async ({ page }) => {
    await page.goto("/course-finder")
    await expect(
      page.getByRole("heading", { name: "Course Finder" }),
    ).toBeVisible()

    const search = page.getByPlaceholder("Cari mata kuliah atau kode")
    await expect(search).toBeVisible()
    await search.fill("AGI101")

    await expect(
      page.getByRole("button", { name: "Lihat detail Agama Islam 1" }),
    ).toBeVisible()
  })
})
