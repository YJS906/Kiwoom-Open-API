import { Eye } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { CandidateStock } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function WatchingPanel({
  items,
  onSelect
}: {
  items: CandidateStock[];
  onSelect: (symbol: string) => void;
}) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <Eye className="h-4 w-4 text-warning" />
        <div>
          <h2 className="text-sm font-semibold text-text">눌림목 감시중</h2>
          <p className="mt-1 text-xs text-muted">일봉 추세는 유지되지만 아직 진입 트리거가 완성되지 않은 종목</p>
        </div>
      </div>
      <div className="space-y-3">
        {items.length === 0 ? (
          <p className="text-sm text-muted">감시중 종목이 없습니다.</p>
        ) : (
          items.slice(0, 8).map((item) => (
            <button
              key={item.symbol}
              onClick={() => onSelect(item.symbol)}
              className="w-full rounded-2xl border border-border/70 bg-panelMuted/50 p-3 text-left transition hover:border-accent/50"
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-text">{item.name}</div>
                  <div className="text-xs text-muted">{item.symbol}</div>
                </div>
                <Badge>{item.state}</Badge>
              </div>
              <div className="mt-2 text-xs text-muted">업데이트 {formatDateTime(item.updated_at)}</div>
            </button>
          ))
        )}
      </div>
    </Card>
  );
}

