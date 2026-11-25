import {
  useEffect,
  useRef,
  useState,
  type JSX,
  type KeyboardEvent,
} from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/shared/utils"

export type ComboboxOption = {
  value: string
  label: string
  hint?: string
}

export type SearchableComboboxProps = {
  id: string
  label?: string
  options: ComboboxOption[]
  value: string
  onChange: (value: string) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyLabel?: string
  disabled?: boolean
  className?: string
  describeBy?: string
}

export default function SearchableCombobox(
  props: SearchableComboboxProps,
): JSX.Element {
  const {
    id,
    label,
    options,
    value,
    onChange,
    placeholder = "Pilih opsi",
    searchPlaceholder = "Cari opsi",
    emptyLabel = "Tidak ada pilihan.",
    disabled = false,
    className,
    describeBy,
  } = props

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [activeIndex, setActiveIndex] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const labelId = `${id}-label`
  const panelId = `${id}-panel`
  const listId = `${id}-listbox`

  const selected = options.find((option) => option.value === value)
  const normalizedQuery = query.trim().toLowerCase()
  const filteredOptions = normalizedQuery
    ? options.filter(
        (option) =>
          option.label.toLowerCase().includes(normalizedQuery) ||
          (option.hint ?? "").toLowerCase().includes(normalizedQuery),
      )
    : options

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target
      if (target instanceof Node && rootRef.current?.contains(target)) return
      setOpen(false)
      setQuery("")
    }

    document.addEventListener("pointerdown", handlePointerDown)
    return () => document.removeEventListener("pointerdown", handlePointerDown)
  }, [open])

  const close = () => {
    setOpen(false)
    setQuery("")
    triggerRef.current?.focus()
  }

  const select = (optionValue: string) => {
    onChange(optionValue)
    close()
  }

  const openPanel = () => {
    if (disabled) return
    setQuery("")
    setActiveIndex(0)
    setOpen(true)
  }

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault()
      openPanel()
    } else if (event.key === "Escape" && open) {
      event.preventDefault()
      close()
    }
  }

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setActiveIndex((index) =>
        filteredOptions.length === 0 ? 0 : (index + 1) % filteredOptions.length,
      )
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      setActiveIndex((index) =>
        filteredOptions.length === 0
          ? 0
          : (index - 1 + filteredOptions.length) % filteredOptions.length,
      )
    } else if (event.key === "Enter") {
      event.preventDefault()
      const option = filteredOptions[activeIndex]
      if (option) select(option.value)
    } else if (event.key === "Escape") {
      event.preventDefault()
      close()
    }
  }

  const activeOption = filteredOptions[activeIndex]

  return (
    <div
      ref={rootRef}
      className={cn(
        "relative w-full",
        disabled && "cursor-not-allowed opacity-60",
        className,
      )}
    >
      {label && (
        <label
          id={labelId}
          htmlFor={`${id}-trigger`}
          className="mb-1.5 block text-xs font-semibold text-navy"
        >
          {label}
        </label>
      )}
      <button
        ref={triggerRef}
        id={`${id}-trigger`}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-controls={panelId}
        aria-haspopup="listbox"
        aria-labelledby={label ? labelId : undefined}
        aria-describedby={describeBy}
        disabled={disabled}
        onClick={() => (open ? close() : openPanel())}
        onKeyDown={handleTriggerKeyDown}
        className={cn(
          "flex min-h-10 w-full items-center justify-between gap-2 rounded-lg border border-border bg-white px-3 text-left text-xs text-navy",
          "hover:border-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold",
          "disabled:cursor-not-allowed disabled:opacity-60",
        )}
      >
        <span className={cn("truncate", !selected && "text-navy/60")}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn("shrink-0 text-navy/60", open && "rotate-180")}
          size={16}
        />
      </button>
      {open && (
        <div
          id={panelId}
          className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-navy/20 bg-white shadow-md"
        >
          <input
            ref={inputRef}
            id={`${id}-search`}
            type="search"
            role="searchbox"
            value={query}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={
              activeOption ? `${id}-option-${activeIndex}` : undefined
            }
            placeholder={searchPlaceholder}
            disabled={disabled}
            onChange={(event) => {
              setQuery(event.target.value)
              setActiveIndex(0)
            }}
            onKeyDown={handleInputKeyDown}
            className="min-h-10 w-full border-b border-navy/20 bg-warm-bg px-3 text-xs text-navy placeholder:text-navy/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold"
          />
          <ul
            id={listId}
            role="listbox"
            aria-labelledby={label ? labelId : `${id}-trigger`}
            className="max-h-52 overflow-y-auto py-1"
          >
            {filteredOptions.length === 0 ? (
              <li className="min-h-9 px-3 py-2 text-xs text-navy/60">
                {emptyLabel}
              </li>
            ) : (
              filteredOptions.map((option, index) => (
                <li
                  key={option.value}
                  id={`${id}-option-${index}`}
                  role="option"
                  aria-selected={option.value === value}
                  onClick={() => select(option.value)}
                  onMouseEnter={() => setActiveIndex(index)}
                  className={cn(
                    "flex min-h-9 cursor-pointer items-center justify-between gap-2 px-3 py-2 text-xs text-navy",
                    index === activeIndex && "bg-navy/5",
                    option.value === value && "font-semibold",
                  )}
                >
                  <span className="truncate">{option.label}</span>
                  {option.hint && (
                    <span className="shrink-0 text-navy/60">{option.hint}</span>
                  )}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
