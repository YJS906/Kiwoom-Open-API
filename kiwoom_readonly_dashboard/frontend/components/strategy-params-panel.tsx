import { Settings2 } from "lucide-react";

import { formatKrw } from "@/lib/format";
import type { StrategyDashboardSnapshot } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function StrategyParamsPanel({ snapshot }: { snapshot: StrategyDashboardSnapshot | null }) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <Settings2 className="h-4 w-4 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-text">전략 파라미터</h2>
          <p className="mt-1 text-xs text-muted">현재 엔진이 실제로 적용 중인 설정 값</p>
        </div>
      </div>
      {!snapshot ? (
        <p className="text-sm text-muted">전략 스냅샷을 기다리는 중입니다.</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Profile" value={snapshot.config.strategy.strategy_profile} />
            <Metric label="Condition" value={snapshot.config.scanner.condition_name} />
            <Metric label="Refresh" value={`${snapshot.config.scanner.refresh_seconds}s`} />
            <Metric label="Trigger TF" value={snapshot.config.strategy.trigger_timeframe} />
            <Metric label="Breakout Vol" value={`${snapshot.config.strategy.breakout_volume_multiplier.toFixed(1)}x`} />
            <Metric label="Box Window" value={`${snapshot.config.strategy.box_window_days}d`} />
            <Metric
              label="Box Range"
              value={`${(snapshot.config.strategy.box_max_range_pct * 100).toFixed(1)}%`}
            />
            <Metric label="Support Ref" value={snapshot.config.strategy.support_reference} />
            <Metric
              label="Support Tol"
              value={`${(snapshot.config.strategy.support_tolerance_pct * 100).toFixed(1)}%`}
            />
            <Metric label="Order Type" value={snapshot.config.execution.order_type} />
            <Metric label="Stop Loss" value={`${(snapshot.config.risk.stop_loss_pct * 100).toFixed(1)}%`} />
            <Metric
              label="Take Profit"
              value={`${(snapshot.config.risk.take_profit_pct * 100).toFixed(1)}%`}
            />
            <Metric label="Paper Cash" value={formatKrw(snapshot.session.paper_cash_balance_krw)} />
            <Metric label="Daily Loss" value={formatKrw(snapshot.session.daily_loss_krw)} />
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge className={snapshot.config.execution.paper_trading ? "text-success" : "text-danger"}>
              {snapshot.config.execution.paper_trading
                ? "PAPER TRADING"
                : snapshot.config.execution.mock_order_enabled
                  ? "KIWOOM MOCK ORDER MODE"
                  : "BROKER MODE"}
            </Badge>
            <Badge>{snapshot.config.execution.auto_buy_enabled ? "AUTO BUY ON" : "AUTO BUY OFF"}</Badge>
            <Badge>{snapshot.config.execution.use_mock_only ? "MOCK ONLY" : "NO MOCK GUARD"}</Badge>
            <Badge>
              {snapshot.config.execution.mock_order_enabled ? "MOCK API ORDER ON" : "MOCK API ORDER OFF"}
            </Badge>
          </div>
        </div>
      )}
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-panelMuted/50 p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 font-medium text-text">{value}</div>
    </div>
  );
}
