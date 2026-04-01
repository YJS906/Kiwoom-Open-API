import { ClipboardList } from "lucide-react";

import { formatDateTime, formatKrw } from "@/lib/format";
import type { FillEvent, OrderIntent } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function OrderLogPanel({
  orders,
  fills
}: {
  orders: OrderIntent[];
  fills: FillEvent[];
}) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <ClipboardList className="h-4 w-4 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-text">오늘 주문 로그</h2>
          <p className="mt-1 text-xs text-muted">전략이 만든 주문 의도와 최근 체결 기록</p>
        </div>
      </div>
      <div className="space-y-4">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Orders</div>
          <div className="space-y-2">
            {orders.length === 0 ? (
              <p className="text-sm text-muted">주문 로그가 없습니다.</p>
            ) : (
              orders.slice(0, 5).map((order) => (
                <div key={order.id} className="rounded-2xl border border-border/70 bg-panelMuted/50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-text">
                      {order.name} {order.side.toUpperCase()} {order.quantity}
                    </div>
                    <Badge>{order.state}</Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted">
                    {formatDateTime(order.updated_at)} / {order.order_type} / {formatKrw(order.desired_price ?? 0)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Fills</div>
          <div className="space-y-2">
            {fills.length === 0 ? (
              <p className="text-sm text-muted">체결 로그가 없습니다.</p>
            ) : (
              fills.slice(0, 5).map((fill) => (
                <div key={fill.id} className="rounded-2xl border border-success/20 bg-success/10 p-3">
                  <div className="font-medium text-green-100">
                    {fill.name} {fill.side.toUpperCase()} {fill.quantity}
                  </div>
                  <div className="mt-2 text-xs text-green-200/80">
                    {formatDateTime(fill.filled_at)} / {formatKrw(fill.price)} / {formatKrw(fill.fill_value_krw)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

