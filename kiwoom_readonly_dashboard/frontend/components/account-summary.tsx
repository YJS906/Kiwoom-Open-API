import {
  ArrowDownRight,
  ArrowUpRight,
  Coins,
  Landmark,
  PieChart,
  Wallet,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatKrw, formatPercent, formatSignedKrw } from "@/lib/format";
import type { AccountSummary as AccountSummaryType } from "@/types/dashboard";

const items = [
  { key: "total_evaluation_amount", label: "총 평가금액", icon: PieChart },
  { key: "total_profit_loss", label: "총 손익", icon: ArrowUpRight },
  { key: "total_profit_rate", label: "수익률", icon: ArrowDownRight },
  { key: "holdings_count", label: "보유 종목 수", icon: Coins },
  { key: "deposit", label: "예수금", icon: Wallet },
  { key: "orderable_amount", label: "주문가능금액", icon: Wallet },
  { key: "estimated_assets", label: "추정 자산", icon: Landmark },
] as const;

export function AccountSummary({
  summary,
  loading,
}: {
  summary: AccountSummaryType | null;
  loading: boolean;
}) {
  return (
    <section className="grid grid-cols-2 gap-4 xl:grid-cols-7">
      {items.map(({ key, label, icon: Icon }) => (
        <Card key={key} className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <span className="text-sm text-muted">{label}</span>
            <Icon className="h-4 w-4 text-accent" />
          </div>
          {loading || !summary ? (
            <Skeleton className="h-8 w-full" />
          ) : (
            <div className="space-y-1">
              <div className="text-2xl font-semibold tracking-tight text-text">
                {renderValue(key, summary)}
              </div>
              <p className="text-xs text-muted">키움 계좌 스냅샷 기준으로 갱신됩니다.</p>
            </div>
          )}
        </Card>
      ))}
    </section>
  );
}

function renderValue(
  key: (typeof items)[number]["key"],
  summary: AccountSummaryType,
) {
  switch (key) {
    case "total_evaluation_amount":
      return formatKrw(summary.total_evaluation_amount);
    case "total_profit_loss":
      return formatSignedKrw(summary.total_profit_loss);
    case "total_profit_rate":
      return formatPercent(summary.total_profit_rate);
    case "holdings_count":
      return `${summary.holdings_count}개`;
    case "deposit":
      return formatKrw(summary.deposit);
    case "orderable_amount":
      return formatKrw(summary.orderable_amount);
    case "estimated_assets":
      return formatKrw(summary.estimated_assets);
  }
}
