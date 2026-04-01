import { CheckCircle2, CircleSlash2, Target } from "lucide-react";

import { formatKrw } from "@/lib/format";
import type { StrategySymbolDetail } from "@/types/dashboard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function StrategyExplainer({
  detail,
  loading
}: {
  detail: StrategySymbolDetail | null;
  loading: boolean;
}) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <Target className="h-4 w-4 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-text">전략 설명 카드</h2>
          <p className="mt-1 text-xs text-muted">왜 통과했는지, 왜 차단됐는지, 현재 기준 가격은 어디인지 설명합니다.</p>
        </div>
      </div>
      {loading || !detail ? (
        <p className="text-sm text-muted">선택 종목의 전략 판단을 불러오는 중입니다.</p>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {detail.decision ? (
              <Badge className={detail.decision.passed ? "text-success" : "text-warning"}>
                {detail.decision.stage}
              </Badge>
            ) : null}
            {detail.candidate ? <Badge>{detail.candidate.state}</Badge> : null}
          </div>
          {detail.levels.length ? (
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              {detail.levels.map((level) => (
                <div key={`${level.kind}-${level.label}`} className="rounded-2xl border border-border/70 bg-panelMuted/50 p-3">
                  <div className="text-xs text-muted">{level.label}</div>
                  <div className="mt-1 font-medium text-text">{formatKrw(level.price)}</div>
                </div>
              ))}
            </div>
          ) : null}
          <div className="space-y-3">
            {detail.explanation_cards.length === 0 ? (
              <p className="text-sm text-muted">전략 설명이 아직 없습니다.</p>
            ) : (
              detail.explanation_cards.map((item, index) => (
                <div key={`${item}-${index}`} className="flex gap-3 rounded-2xl border border-border/70 bg-panelMuted/50 p-3">
                  {item.toLowerCase().includes("blocked") ? (
                    <CircleSlash2 className="mt-0.5 h-4 w-4 text-danger" />
                  ) : (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-success" />
                  )}
                  <p className="text-sm text-muted">{item}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

