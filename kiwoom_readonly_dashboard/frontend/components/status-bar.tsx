import type { ReactNode } from "react";
import { Activity, BrainCircuit, Newspaper, Radio, RefreshCcw } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { StatusPanel as StatusPanelType } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function StatusBar({
  status,
  realtimeConnected
}: {
  status: StatusPanelType | null;
  realtimeConnected: boolean;
}) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-text">API 상태</h2>
          <p className="mt-1 text-xs text-muted">키움 연결, 뉴스 공급원, 전략 엔진 상태를 함께 보여줍니다.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          <RefreshCcw className="h-4 w-4" />
          <span>{formatDateTime(status?.last_refresh_at)}</span>
        </div>
      </div>
      <div className="grid gap-3">
        <StatusItem
          icon={<Activity className="h-4 w-4" />}
          label="Kiwoom REST"
          status={status?.kiwoom_rest.status ?? "unknown"}
          detail={status?.kiwoom_rest.detail ?? null}
        />
        <StatusItem
          icon={<Radio className="h-4 w-4" />}
          label="Kiwoom WebSocket"
          status={realtimeConnected ? "connected" : status?.kiwoom_websocket.status ?? "unknown"}
          detail={status?.kiwoom_websocket.detail ?? null}
        />
        <StatusItem
          icon={<BrainCircuit className="h-4 w-4" />}
          label="Strategy Engine"
          status={status?.strategy_engine?.status ?? "unknown"}
          detail={status?.strategy_engine?.detail ?? null}
        />
        <StatusItem
          icon={<Newspaper className="h-4 w-4" />}
          label="News Provider"
          status={status?.news_provider.status ?? "unknown"}
          detail={status?.news_provider.detail ?? null}
        />
      </div>
      <div className="mt-5 space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted">Recent Errors</div>
        {status?.recent_errors?.length ? (
          <ul className="space-y-2">
            {status.recent_errors.slice(-5).map((error) => (
              <li
                key={error}
                className="rounded-xl border border-danger/20 bg-danger/5 px-3 py-2 text-xs text-red-200"
              >
                {error}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">최근 오류가 없습니다.</p>
        )}
      </div>
    </Card>
  );
}

function StatusItem({
  icon,
  label,
  status,
  detail
}: {
  icon: ReactNode;
  label: string;
  status: string;
  detail: string | null;
}) {
  const tone =
    status === "connected" || status === "ready" || status === "running"
      ? "border-success/30 bg-success/10 text-success"
      : status === "degraded" || status === "misconfigured" || status === "reconnecting"
        ? "border-warning/30 bg-warning/10 text-warning"
        : "border-border/70 bg-panelMuted/70 text-muted";

  return (
    <div className="rounded-2xl border border-border/70 bg-panelMuted/50 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-text">
          {icon}
          <span>{label}</span>
        </div>
        <Badge className={tone}>{status}</Badge>
      </div>
      <p className="mt-2 text-xs text-muted">{detail ?? "정상 상태"}</p>
    </div>
  );
}

