import { formatNumber } from "@/lib/format";
import type { OrderbookSnapshot } from "@/types/dashboard";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function OrderbookPanel({
  orderbook,
  loading
}: {
  orderbook: OrderbookSnapshot | null;
  loading: boolean;
}) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-text">호가 일부</h2>
          <p className="mt-1 text-xs text-muted">상위 5개 호가 잔량</p>
        </div>
        <span className="text-xs text-muted">{orderbook?.timestamp ?? "-"}</span>
      </div>
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full rounded-xl" />
          ))}
        </div>
      ) : !orderbook ? (
        <div className="text-sm text-muted">호가 데이터가 아직 없습니다.</div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-danger/20 bg-danger/5 p-3">
            <div className="mb-3 text-xs font-semibold text-danger">매도 호가</div>
            <div className="space-y-2">
              {orderbook.asks.map((level) => (
                <div key={`ask-${level.price}`} className="flex items-center justify-between text-sm">
                  <span className="text-danger">{formatNumber(level.price)}</span>
                  <span className="text-muted">{formatNumber(level.quantity)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-success/20 bg-success/5 p-3">
            <div className="mb-3 text-xs font-semibold text-success">매수 호가</div>
            <div className="space-y-2">
              {orderbook.bids.map((level) => (
                <div key={`bid-${level.price}`} className="flex items-center justify-between text-sm">
                  <span className="text-success">{formatNumber(level.price)}</span>
                  <span className="text-muted">{formatNumber(level.quantity)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
