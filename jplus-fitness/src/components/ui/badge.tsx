import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-white/[0.03] px-3.5 py-1.5 text-xs font-medium tracking-wide text-gray-300 uppercase",
        className
      )}
      {...props}
    />
  );
}
