import { expect, type Page } from "@playwright/test"

export const ACCOUNTS = {
  admin: {
    identifier: "admin@ftmm.unair.ac.id",
    password: "AdminFTMM2026!",
  },
  student: {
    identifier: "mahasiswa.tsd@ftmm.unair.ac.id",
    password: "Mahasiswa2026!",
  },
} as const

export const STORAGE_STATE = {
  admin: "tests/e2e/.auth/admin.json",
  student: "tests/e2e/.auth/student.json",
} as const

export interface Credential {
  identifier: string
  password: string
}

export async function fillLogin(page: Page, account: Credential) {
  await page.goto("/")
  await page.locator("#login-identifier").fill(account.identifier)
  await page.locator("#login-password").fill(account.password)
}

export async function login(page: Page, account: Credential) {
  await fillLogin(page, account)
  await page.getByRole("button", { name: "Masuk ke Dashboard" }).click()
  await page.waitForURL("**/dashboard")
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
}
