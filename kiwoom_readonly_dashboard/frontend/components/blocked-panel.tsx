import { ShieldX } from "lucide-react";

import type { CandidateStock } from "@/types/dashboard";
import { Card } from "@/components/ui/card";

export function BlockedPanel({ items }: { items: CandidateStock[] }) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <ShieldX className="h-4 w-4 text-danger" />
        <div>
          <h2 className="text-sm font-semibold text-text">차단된 종목</h2>
          <p className="mt-1 text-xs text-muted">리스크 규칙으로 진입이 거부된 종목과 사유</p>
        </div>
      </div>
      <div className="space-y-3">
        {items.length === 0 ? (
          <p className="text-sm text-muted">차단된 종목이 없습니다.</p>
        ) : (
          items.slice(0, 8).map((item) => (
            <div key={item.symbol} className="rounded-2xl border border-danger/20 bg-danger/10 p-3">
              <div className="font-medium text-red-100">{item.name}</div>
              <div className="mt-1 text-xs text-red-200/80">{item.symbol}</div>
              <p className="mt-2 text-sm text-red-100/90">{item.blocked_reason ?? "No reason available."}</p>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

