import type { ComponentType } from "react";
import { Activity, ArrowDown, ArrowUp, BookmarkPlus, ChartCandlestick } from "lucide-react";

import { formatKrw, formatNumber, formatPercent, formatSignedKrw } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StockDetailResponse } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function StockHeader({
  detail,
  loading,
  onAddWatchlist
}: {
  detail: StockDetailResponse | null;
  loading: boolean;
  onAddWatchlist: () => void;
}) {
  return (
    <Card className="p-5">
      {loading || !detail ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-tight text-text">
                  {detail.quote.name}
                </h1>
                <Badge>{detail.quote.symbol}</Badge>
                {detail.quote.market_phase ? <Badge>{detail.quote.market_phase}</Badge> : null}
              </div>
              <div className="mt-3 flex items-end gap-4">
                <p className="text-4xl font-semibold text-text">
                  {formatKrw(detail.quote.current_price)}
                </p>
                <p
                  className={cn(
                    "pb-1 text-sm font-semibold",
                    detail.quote.diff_from_previous_close >= 0 ? "text-success" : "text-danger"
                  )}
                >
                  {formatSignedKrw(detail.quote.diff_from_previous_close)} ·{" "}
                  {formatPercent(detail.quote.change_rate)}
                </p>
              </div>
            </div>
            <Button onClick={onAddWatchlist} className="gap-2">
              <BookmarkPlus className="h-4 w-4" />
              관심종목 추가
            </Button>
          </div>
          <div className="grid grid-cols-4 gap-3 xl:grid-cols-8">
            <Metric label="거래량" value={formatNumber(detail.quote.volume)} icon={Activity} />
            <Metric label="시가" value={formatKrw(detail.quote.open_price)} icon={ChartCandlestick} />
            <Metric label="고가" value={formatKrw(detail.quote.high_price)} icon={ArrowUp} />
            <Metric label="저가" value={formatKrw(detail.quote.low_price)} icon={ArrowDown} />
            <Metric label="전일종가" value={formatKrw(detail.quote.previous_close)} />
            <Metric label="최우선 매도" value={formatKrw(detail.quote.best_ask ?? 0)} />
            <Metric label="최우선 매수" value={formatKrw(detail.quote.best_bid ?? 0)} />
            <Metric label="시장" value={detail.quote.market_name ?? "KRX"} />
          </div>
        </div>
      )}
    </Card>
  );
}

function Metric({
  label,
  value,
  icon: Icon
}: {
  label: string;
  value: string;
  icon?: ComponentType<{ className?: string }>;
}) {
  return (
    <div className="rounded-2xl border border-border/70 bg-panelMuted/60 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-muted">
        {Icon ? <Icon className="h-3.5 w-3.5" /> : null}
        <span>{label}</span>
      </div>
      <div className="text-sm font-semibold text-text">{value}</div>
    </div>
  );
}
