import { AlertCircle } from "lucide-react"

export interface FormFieldErrorProps {
  id: string
  message: string | null
}

export default function FormFieldError({ id, message }: FormFieldErrorProps) {
  if (!message) return null
  return (
    <p
      id={id}
      role="alert"
      className="mt-1 flex items-start gap-1 text-xs text-orange"
    >
      <AlertCircle aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>
        <span className="sr-only">Kesalahan: </span>
        {message}
      </span>
    </p>
  )
}
