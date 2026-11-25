import { cn } from "@/shared/utils"
import { prodiLabel, prodiTone } from "@/shared/domain/prodi"

export interface ProdiBadgeProps {
  code?: string | null
  className?: string
}

export default function ProdiBadge({ code, className }: ProdiBadgeProps) {
  const label = prodiLabel(code)
  const tone = prodiTone(code)

  return (
    <span
      aria-label={`Program studi ${label}`}
      className={cn(
        "inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        tone.text,
        tone.border,
        tone.tint,
        className,
      )}
    >
      {label}
    </span>
  )
}
