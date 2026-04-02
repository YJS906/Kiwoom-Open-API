import { Activity, AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatKrw, formatNumber, formatPercent } from "@/lib/format";
import type { RealtimeHigh52Response } from "@/types/dashboard";

export function RealtimeHigh52Panel({
  snapshot,
  selectedSymbol,
  onSelect
}: {
  snapshot: RealtimeHigh52Response | null;
  selectedSymbol: string | null;
  onSelect: (symbol: string) => void;
}) {
  const items = snapshot?.items ?? [];

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border/80 px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-text">실시간 52주 신고가</h2>
              <p className="mt-1 text-xs text-muted">
                Kiwoom REST `ka10016` official feed
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge>{snapshot?.environment ?? "mock"}</Badge>
            <Badge>{snapshot?.status ?? "loading"}</Badge>
          </div>
        </div>
        {snapshot?.reason ? (
          <div className="mt-3 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-yellow-100">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{snapshot.reason}</p>
            </div>
          </div>
        ) : null}
      </div>
      <div className="max-h-[340px] overflow-auto">
        {!snapshot ? (
          <div className="p-5 text-sm text-muted">실시간 52주 신고가 목록을 불러오는 중입니다.</div>
        ) : items.length === 0 ? (
          <div className="p-5 text-sm text-muted">
            표시할 종목이 없습니다. 현재 설정에서는 mock data 또는 empty response 일 수 있습니다.
          </div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-panel/95 text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">종목</th>
                <th className="px-4 py-3">현재가</th>
                <th className="px-4 py-3">등락률</th>
                <th className="px-4 py-3">거래량</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.symbol}
                  onClick={() => onSelect(item.symbol)}
                  className={`cursor-pointer border-t border-border/60 transition hover:bg-panelMuted/60 ${
                    selectedSymbol === item.symbol ? "bg-accent/10" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-text">{item.name}</div>
                    <div className="text-xs text-muted">{item.symbol}</div>
                  </td>
                  <td className="px-4 py-3 text-text">{formatKrw(item.current_price)}</td>
                  <td className={`px-4 py-3 ${item.change_rate >= 0 ? "text-success" : "text-danger"}`}>
                    {formatPercent(item.change_rate)}
                  </td>
                  <td className="px-4 py-3 text-muted">{formatNumber(item.volume)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}
