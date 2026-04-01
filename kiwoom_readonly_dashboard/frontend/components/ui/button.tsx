import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Button({
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-xl border border-border bg-panelMuted px-4 py-2 text-sm font-medium text-text transition hover:border-accent/60 hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
