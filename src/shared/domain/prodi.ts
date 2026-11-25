export type ProdiCode = "TSD" | "RN" | "TI" | "TRKB" | "TE"

export const PRODI_CODES: ProdiCode[] = ["TSD", "RN", "TI", "TRKB", "TE"]

export interface ProdiTone {
  text: string
  border: string
  tint: string
  leftVar: string
}

const TONES: Record<ProdiCode, ProdiTone> = {
  TSD: {
    text: "text-prodi-tsd",
    border: "border-prodi-tsd",
    tint: "bg-prodi-tsd/10",
    leftVar: "var(--color-prodi-tsd)",
  },
  RN: {
    text: "text-prodi-rn",
    border: "border-prodi-rn",
    tint: "bg-prodi-rn/10",
    leftVar: "var(--color-prodi-rn)",
  },
  TI: {
    text: "text-prodi-ti",
    border: "border-prodi-ti",
    tint: "bg-prodi-ti/10",
    leftVar: "var(--color-prodi-ti)",
  },
  TRKB: {
    text: "text-prodi-trkb",
    border: "border-prodi-trkb",
    tint: "bg-prodi-trkb/10",
    leftVar: "var(--color-prodi-trkb)",
  },
  TE: {
    text: "text-prodi-te",
    border: "border-prodi-te",
    tint: "bg-prodi-te/10",
    leftVar: "var(--color-prodi-te)",
  },
}

const NEUTRAL_TONE: ProdiTone = {
  text: "text-muted",
  border: "border-border",
  tint: "bg-secondary",
  leftVar: "var(--color-border)",
}

function normalize(code?: string | null): ProdiCode | null {
  if (!code) return null
  const normalized = code.trim().toUpperCase()
  return PRODI_CODES.includes(normalized as ProdiCode)
    ? normalized as ProdiCode
    : null
}

export function prodiTone(code?: string | null): ProdiTone {
  const normalized = normalize(code)
  return normalized ? TONES[normalized] : NEUTRAL_TONE
}

export function prodiLabel(code?: string | null): string {
  const normalized = code?.trim().toUpperCase()
  return normalized ? normalized : "—"
}
