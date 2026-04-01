import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "glass rounded-2xl border border-border/70 bg-panel/85 shadow-soft",
        className
      )}
      {...props}
    />
  );
}
