import { expect, test } from "@playwright/test"
import { ACCOUNTS, STORAGE_STATE, fillLogin, login } from "./support/app"

test.describe("Kredensial", () => {
  test("menolak kredensial yang salah", async ({ page }) => {
    await fillLogin(page, {
      identifier: ACCOUNTS.admin.identifier,
      password: "kata-sandi-salah",
    })
    await page.getByRole("button", { name: "Masuk ke Dashboard" }).click()

    await expect(
      page.getByText("NIM/Email atau kata sandi tidak valid"),
    ).toBeVisible()
    await expect(page).not.toHaveURL(/\/dashboard$/)
  })
})

test.describe("Sesi mahasiswa", () => {
  test("mahasiswa masuk lalu keluar", async ({ page }) => {
    await login(page, ACCOUNTS.student)
    await page.getByRole("button", { name: "Logout" }).click()
    await expect(
      page.getByRole("heading", { name: "Konfirmasi Keluar" }),
    ).toBeVisible()
    await page.getByRole("button", { name: "Ya, Keluar" }).click()
    await expect(
      page.getByRole("heading", { name: "Selamat Datang" }),
    ).toBeVisible()
    await expect(
      page.getByRole("button", { name: "Masuk ke Dashboard" }),
    ).toBeVisible()
  })
})

test.describe("Rute terlindungi", () => {
  test.use({ storageState: STORAGE_STATE.student })

  test("rute khusus admin dialihkan untuk mahasiswa", async ({ page }) => {
    await page.goto("/admin-accounts")
    await page.waitForURL("**/dashboard")
    await expect(
      page.getByRole("heading", { name: "Manajemen Akun" }),
    ).toHaveCount(0)
    await expect(
      page.getByRole("link", { name: "Manajemen Akun" }),
    ).toHaveCount(0)
  })
})
