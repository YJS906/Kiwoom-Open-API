import { Star, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function Watchlist({
  items,
  selectedSymbol,
  onSelect,
  onRemove
}: {
  items: string[];
  selectedSymbol: string | null;
  onSelect: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border/80 px-5 py-4">
        <h2 className="text-sm font-semibold text-text">관심종목</h2>
        <p className="mt-1 text-xs text-muted">브라우저 로컬 저장</p>
      </div>
      {items.length === 0 ? (
        <div className="p-6 text-sm text-muted">아직 추가된 종목이 없습니다.</div>
      ) : (
        <ul className="divide-y divide-border/70">
          {items.map((symbol) => (
            <li key={symbol} className="px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => onSelect(symbol)}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-2 py-2 text-left text-sm transition",
                    selectedSymbol === symbol
                      ? "bg-accent/10 text-text"
                      : "text-muted hover:bg-panelMuted/60 hover:text-text"
                  )}
                >
                  <Star className="h-4 w-4 text-warning" />
                  <span>{symbol}</span>
                </button>
                <Button
                  type="button"
                  onClick={() => onRemove(symbol)}
                  className="h-9 w-9 px-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
