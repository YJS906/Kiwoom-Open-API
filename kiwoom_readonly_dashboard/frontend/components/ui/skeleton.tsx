import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-xl bg-gradient-to-r from-panelMuted via-slate-800 to-panelMuted",
        className
      )}
    />
  );
}
