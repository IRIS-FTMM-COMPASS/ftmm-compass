import fs from "node:fs"
import type { Page } from "@playwright/test"

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

interface StorageEntry {
  name: string
  value: string
}

export function storageToken(path: string): string {
  const state = JSON.parse(fs.readFileSync(path, "utf8")) as {
    origins?: { localStorage?: StorageEntry[] }[]
  }
  const token = state.origins
    ?.flatMap((origin) => origin.localStorage ?? [])
    .find((entry) => entry.name === "auth_token")?.value
  if (!token) throw new Error(`Token autentikasi tidak ditemukan di ${path}.`)
  return token
}

export async function fillLogin(page: Page, account: Credential) {
  await page.goto("/")
  await page.locator("#login-identifier").fill(account.identifier)
  await page.locator("#login-password").fill(account.password)
}
