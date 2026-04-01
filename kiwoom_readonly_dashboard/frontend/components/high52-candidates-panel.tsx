import { Radar } from "lucide-react";

import { formatKrw, formatPercent } from "@/lib/format";
import type { CandidateStock } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function High52CandidatesPanel({
  items,
  selectedSymbol,
  onSelect
}: {
  items: CandidateStock[];
  selectedSymbol: string | null;
  onSelect: (symbol: string) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border/80 px-5 py-4">
        <div className="flex items-center gap-2">
          <Radar className="h-4 w-4 text-accent" />
          <div>
            <h2 className="text-sm font-semibold text-text">52주 신고가 후보군</h2>
            <p className="mt-1 text-xs text-muted">조건검색 또는 안전 fallback으로 추린 후보 목록</p>
          </div>
        </div>
      </div>
      <div className="max-h-[340px] overflow-auto">
        {items.length === 0 ? (
          <div className="p-5 text-sm text-muted">현재 후보군이 없습니다.</div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-panel/95 text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">종목</th>
                <th className="px-4 py-3">현재가</th>
                <th className="px-4 py-3">등락률</th>
                <th className="px-4 py-3">상태</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={`${item.symbol}-${item.updated_at}`}
                  onClick={() => onSelect(item.symbol)}
                  className={`cursor-pointer border-t border-border/60 transition hover:bg-panelMuted/60 ${
                    selectedSymbol === item.symbol ? "bg-accent/10" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-text">{item.name}</div>
                    <div className="text-xs text-muted">{item.symbol}</div>
                  </td>
                  <td className="px-4 py-3 text-text">{formatKrw(item.last_price ?? 0)}</td>
                  <td className={`px-4 py-3 ${(item.change_rate ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                    {formatPercent(item.change_rate ?? 0)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge>{item.state}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}

