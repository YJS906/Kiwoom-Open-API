import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-xl border border-border bg-panelMuted px-4 py-3 text-sm text-text outline-none placeholder:text-muted focus:border-accent/60 focus:ring-2 focus:ring-accent/15",
        className
      )}
      {...props}
    />
  );
}
