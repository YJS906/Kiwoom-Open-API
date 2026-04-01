import { formatKrw, formatPercent, formatSignedKrw } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { HoldingItem } from "@/types/dashboard";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function HoldingsTable({
  items,
  loading,
  selectedSymbol,
  onSelect
}: {
  items: HoldingItem[];
  loading: boolean;
  selectedSymbol: string | null;
  onSelect: (symbol: string) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border/80 px-5 py-4">
        <h2 className="text-sm font-semibold text-text">보유 종목</h2>
        <p className="mt-1 text-xs text-muted">계좌 보유 현황을 선택 종목 패널과 연동합니다.</p>
      </div>
      <div className="max-h-[520px] overflow-auto">
        {loading ? (
          <div className="space-y-3 p-5">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="p-6 text-sm text-muted">보유 종목이 없습니다.</div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-panel/95 text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">종목</th>
                <th className="px-4 py-3">수량</th>
                <th className="px-4 py-3">평균단가</th>
                <th className="px-4 py-3">현재가</th>
                <th className="px-4 py-3">손익</th>
                <th className="px-4 py-3">수익률</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.symbol}
                  onClick={() => onSelect(item.symbol)}
                  className={cn(
                    "cursor-pointer border-t border-border/60 transition hover:bg-panelMuted/60",
                    selectedSymbol === item.symbol && "bg-accent/10"
                  )}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-text">{item.name}</div>
                    <div className="text-xs text-muted">{item.symbol}</div>
                  </td>
                  <td className="px-4 py-3 text-muted">{item.quantity}</td>
                  <td className="px-4 py-3 text-muted">{formatKrw(item.average_price)}</td>
                  <td className="px-4 py-3 text-text">{formatKrw(item.current_price)}</td>
                  <td
                    className={cn(
                      "px-4 py-3",
                      item.evaluation_profit_loss >= 0 ? "text-success" : "text-danger"
                    )}
                  >
                    {formatSignedKrw(item.evaluation_profit_loss)}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-3",
                      item.profit_rate >= 0 ? "text-success" : "text-danger"
                    )}
                  >
                    {formatPercent(item.profit_rate)}
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
