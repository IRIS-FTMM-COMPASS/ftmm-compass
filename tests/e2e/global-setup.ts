import fs from "node:fs/promises"
import path from "node:path"
import { request } from "@playwright/test"
import { ACCOUNTS, STORAGE_STATE, type Credential } from "./support/app"

const HEALTH_URL = "/api/v1/health"
const LOGIN_URL = "/api/v1/auth/login"

function sleep(milliseconds: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>()
  setTimeout(resolve, milliseconds)
  return promise
}

interface LoginResponse {
  access_token: string
  expires_in: number
  user: unknown
}

async function createStorageState(
  baseURL: string,
  account: Credential,
  outputPath: string,
) {
  const context = await request.newContext({ baseURL })
  try {
    let response = await context.post(LOGIN_URL, { data: account })
    if (response.status() === 429) {
      const retryAfter = Number(response.headers()["retry-after"] ?? 60)
      await sleep((Math.max(1, retryAfter) + 1) * 1_000)
      response = await context.post(LOGIN_URL, { data: account })
    }
    if (!response.ok()) {
      throw new Error(
        `Login E2E gagal untuk ${account.identifier}: HTTP ${response.status()}.`,
      )
    }
    const session = (await response.json()) as LoginResponse
    const expiresAt = Date.now() + session.expires_in * 1000
    const state = {
      cookies: [],
      origins: [
        {
          origin: new URL(baseURL).origin,
          localStorage: [
            { name: "auth_token", value: session.access_token },
            {
              name: "auth_user",
              value: JSON.stringify(session.user),
            },
            { name: "auth_expires_at", value: String(expiresAt) },
          ],
        },
      ],
    }
    const absolutePath = path.resolve(process.cwd(), outputPath)
    await fs.mkdir(path.dirname(absolutePath), { recursive: true })
    await fs.writeFile(absolutePath, JSON.stringify(state))
  } finally {
    await context.dispose()
  }
}

export default async function globalSetup() {
  const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8443"
  const context = await request.newContext({ baseURL })
  let lastStatus = 0
  try {
    for (let attempt = 0; attempt < 60; attempt += 1) {
      try {
        const response = await context.get(HEALTH_URL, { timeout: 5_000 })
        lastStatus = response.status()
        if (response.ok()) break
      } catch {
        lastStatus = 0
      }
      if (attempt === 59) {
        throw new Error(
          `Backend tidak siap pada ${baseURL}${HEALTH_URL}; status terakhir ${lastStatus}.`,
        )
      }
      await sleep(1_000)
    }
  } finally {
    await context.dispose()
  }

  await createStorageState(baseURL, ACCOUNTS.admin, STORAGE_STATE.admin)
  await createStorageState(baseURL, ACCOUNTS.student, STORAGE_STATE.student)
}
