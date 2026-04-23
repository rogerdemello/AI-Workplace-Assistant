import * as React from "react"
import Image from "next/image"
import { cn } from "@/lib/utils"

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string
  alt?: string
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, src, alt, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full",
          className
        )}
        {...props}
      >
        {src ? (
          <Image
            src={src}
            alt={alt ?? "Avatar"}
            fill
            sizes="40px"
            className="aspect-square h-full w-full object-cover"
          />
        ) : null}
      </div>
    )
  }
)
Avatar.displayName = "Avatar"

export { Avatar }
