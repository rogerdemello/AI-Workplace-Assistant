import * as React from "react"
import { cn } from "@/lib/utils"

export interface SpinnerProps {
  message?: string
  className?: string
}

const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ message, className }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "fixed inset-0 z-50 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm",
          className
        )}
      >
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" />
        {message && (
          <p className="mt-4 text-sm font-medium text-slate-600">
            {message}
          </p>
        )}
      </div>
    )
  }
)
Spinner.displayName = "Spinner"

export { Spinner }