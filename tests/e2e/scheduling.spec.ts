import { expect, test } from "@playwright/test"
import { STORAGE_STATE } from "./support/app"

test.use({ storageState: STORAGE_STATE.admin })

test.describe("Penjadwalan admin", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/scheduling")
    await expect(
      page.getByRole("heading", { name: "Penjadwalan" }),
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
})

test.describe("Penjadwalan mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test("navigasi mobile dan papan tidak meluber", async ({ page }) => {
    await page.goto("/scheduling")
    await expect(
      page.getByRole("heading", { name: "Penjadwalan" }),
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
