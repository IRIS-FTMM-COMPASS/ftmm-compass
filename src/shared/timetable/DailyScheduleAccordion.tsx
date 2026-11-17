import { useState } from "react"
import { AlertTriangle, ChevronDown, Clock, MapPin } from "lucide-react"
import { cn } from "@/shared/utils"
import { formatTime, type ScheduleItem } from "@/shared/domain/models"

interface DailyScheduleAccordionProps {
  schedule: ScheduleItem[]
  days: readonly string[]
  onItemClick?: (item: ScheduleItem) => void
}

export default function DailyScheduleAccordion({
  schedule,
  days,
  onItemClick,
}: DailyScheduleAccordionProps) {
  const [openDay, setOpenDay] = useState<string | null>(days[0] ?? null)

  return (
    <div className="flex-1 min-h-0 overflow-y-auto md:hidden print:hidden">
      <p className="text-xs text-muted mb-3">
        Pilih hari untuk melihat mata kuliah dan ruang kelas.
      </p>
      <div className="space-y-2">
        {days.map((day) => {
          const items = schedule
            .filter((item) => item.day === day)
            .sort((a, b) => a.start - b.start)
          const isOpen = openDay === day
          const dayId = `jadwal-hari-${day.toLowerCase()}`

          return (
            <section
              key={day}
              className="rounded-xl border border-border bg-surface overflow-hidden"
            >
              <h3>
                <button
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={dayId}
                  onClick={() => setOpenDay(isOpen ? null : day)}
                  className="min-h-11 w-full flex items-center justify-between gap-3 px-3 py-2 text-left cursor-pointer hover:bg-navy/5"
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <span className="font-heading font-bold text-sm text-navy">
                      {day}
                    </span>
                    <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-navy/8 text-navy border border-navy/15">
                      {items.length} kelas
                    </span>
                  </span>
                  <span className="flex items-center gap-2">
                    {items.length > 0 && (
                      <span className="text-[11px] font-mono text-muted hidden sm:inline">
                        {formatTime(items[0].start)}–
                        {formatTime(
                          items[items.length - 1].start +
                            items[items.length - 1].duration,
                        )}
                      </span>
                    )}
                    <ChevronDown
                      className={cn(
                        "w-4 h-4 text-navy transition-transform",
                        isOpen && "rotate-180",
                      )}
                    />
                  </span>
                </button>
              </h3>
              <div
                id={dayId}
                className={cn(
                  "border-t border-border px-3 py-3 space-y-2",
                  !isOpen && "hidden",
                )}
              >
                {items.length === 0 ? (
                  <p className="text-xs text-foreground py-2">
                    Tidak ada kelas pada hari {day}. Pilih hari lain atau
                    tambahkan mata kuliah di tab Roadmap Studi.
                  </p>
                ) : (
                  items.map((item) => {
                    const body = (
                      <span className="flex flex-col gap-1.5 min-w-0">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="font-mono font-bold text-xs text-navy">
                            {item.code}
                          </span>
                          {item.sectionCode && (
                            <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-navy/10 text-navy">
                              {item.sectionCode}
                            </span>
                          )}
                          {item.conflict && (
                            <span className="text-[11px] font-semibold text-danger flex items-center gap-1">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              Bentrok
                            </span>
                          )}
                        </span>
                        <span className="text-sm font-medium text-foreground break-words">
                          {item.course}
                        </span>
                        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5 flex-shrink-0" />
                            {formatTime(item.start)}–
                            {formatTime(item.start + item.duration)}
                          </span>
                          {item.room && (
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
                              {item.room}
                            </span>
                          )}
                        </span>
                      </span>
                    )
                    const classes = cn(
                      "min-h-11 w-full rounded-lg border p-3 text-left",
                      item.conflict
                        ? "border-danger/40 bg-danger/5"
                        : "border-border/80 bg-background",
                      onItemClick && "cursor-pointer hover:border-navy/30",
                    )

                    return onItemClick ? (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => onItemClick(item)}
                        className={classes}
                      >
                        {body}
                      </button>
                    ) : (
                      <div key={item.id} className={classes}>
                        {body}
                      </div>
                    )
                  })
                )}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}
