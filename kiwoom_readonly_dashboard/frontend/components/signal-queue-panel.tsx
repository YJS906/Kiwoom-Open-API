import { Play, Zap } from "lucide-react";

import { formatDateTime, formatKrw } from "@/lib/format";
import type { ExecutionConfig, SignalEvent } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function SignalQueuePanel({
  items,
  executionConfig,
  onExecute,
  executingSignalId,
  onSelectSymbol
}: {
  items: SignalEvent[];
  executionConfig: ExecutionConfig;
  onExecute: (signalId: string) => void;
  executingSignalId: string | null;
  onSelectSymbol: (symbol: string) => void;
}) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <Zap className="h-4 w-4 text-success" />
        <div>
          <h2 className="text-sm font-semibold text-text">진입 신호 대기열</h2>
          <p className="mt-1 text-xs text-muted">자동매수는 기본 비활성화이며, 필요 시 모의주문만 수동 실행합니다.</p>
        </div>
      </div>
      <div className="space-y-3">
        {items.length === 0 ? (
          <p className="text-sm text-muted">대기 중인 신호가 없습니다.</p>
        ) : (
          items.slice(0, 8).map((item) => (
            <div key={item.id} className="rounded-2xl border border-border/70 bg-panelMuted/50 p-4">
              <div className="flex items-start justify-between gap-3">
                <button onClick={() => onSelectSymbol(item.symbol)} className="text-left">
                  <div className="font-medium text-text">{item.name}</div>
                  <div className="text-xs text-muted">{item.symbol}</div>
                </button>
                <Badge>{item.status}</Badge>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-muted">
                <div>Entry: {formatKrw(item.decision.entry_price ?? 0)}</div>
                <div>Stop: {formatKrw(item.decision.stop_price ?? 0)}</div>
                <div>Target: {formatKrw(item.decision.target_price ?? 0)}</div>
                <div>Created: {formatDateTime(item.created_at)}</div>
              </div>
              <p className="mt-3 text-sm text-muted">{item.explanation}</p>
              {!item.risk?.allowed && item.risk?.reasons?.length ? (
                <div className="mt-3 rounded-xl border border-danger/20 bg-danger/10 px-3 py-2 text-xs text-red-200">
                  {item.risk.reasons.join(" / ")}
                </div>
              ) : null}
              <div className="mt-4 flex gap-2">
                <Button
                  onClick={() => onExecute(item.id)}
                  disabled={
                    item.status !== "queued" ||
                    !executionConfig.manual_signal_execution ||
                    executingSignalId === item.id
                  }
                  className="gap-2"
                >
                  <Play className="h-4 w-4" />
                  {executingSignalId === item.id ? "실행 중..." : "모의주문 실행"}
                </Button>
                <Badge className={executionConfig.paper_trading ? "text-success" : "text-danger"}>
                  {executionConfig.paper_trading ? "PAPER" : "REAL"}
                </Badge>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

