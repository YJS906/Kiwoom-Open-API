"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { AlertTriangle, Save } from "lucide-react";

import type { TradingConfig } from "@/types/dashboard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function AdminSettingsPanel({
  config,
  onSave,
  saving
}: {
  config: TradingConfig | null;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  saving: boolean;
}) {
  const [refreshSeconds, setRefreshSeconds] = useState("45");
  const [triggerTimeframe, setTriggerTimeframe] = useState<"15m" | "5m">("15m");
  const [breakoutVolumeMultiplier, setBreakoutVolumeMultiplier] = useState("2.0");
  const [supportReference, setSupportReference] = useState<"breakout" | "ma_fast" | "either" | "both">("either");
  const [supportTolerancePct, setSupportTolerancePct] = useState("0.02");
  const [autoBuyEnabled, setAutoBuyEnabled] = useState(false);
  const [paperTrading, setPaperTrading] = useState(true);
  const [orderType, setOrderType] = useState<"market" | "limit" | "stop_limit">("market");

  useEffect(() => {
    if (!config) return;
    setRefreshSeconds(String(config.scanner.refresh_seconds));
    setTriggerTimeframe(config.strategy.trigger_timeframe);
    setBreakoutVolumeMultiplier(String(config.strategy.breakout_volume_multiplier));
    setSupportReference(config.strategy.support_reference);
    setSupportTolerancePct(String(config.strategy.support_tolerance_pct));
    setAutoBuyEnabled(config.execution.auto_buy_enabled);
    setPaperTrading(config.execution.paper_trading);
    setOrderType(config.execution.order_type);
  }, [config]);

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <div>
          <h2 className="text-sm font-semibold text-text">관리자 설정</h2>
          <p className="mt-1 text-xs text-muted">런타임 override만 저장합니다. 기본 안전값은 유지하세요.</p>
        </div>
      </div>
      <div className="space-y-4">
        <Field label="Scanner refresh (sec)">
          <Input value={refreshSeconds} onChange={(event) => setRefreshSeconds(event.target.value)} />
        </Field>
        <Field label="Trigger timeframe">
          <select
            value={triggerTimeframe}
            onChange={(event) => setTriggerTimeframe(event.target.value as "15m" | "5m")}
            className="w-full rounded-xl border border-border bg-panelMuted px-3 py-2 text-sm text-text outline-none"
          >
            <option value="15m">15m</option>
            <option value="5m">5m</option>
          </select>
        </Field>
        <Field label="Breakout volume multiplier">
          <Input
            value={breakoutVolumeMultiplier}
            onChange={(event) => setBreakoutVolumeMultiplier(event.target.value)}
          />
        </Field>
        <Field label="Support reference">
          <select
            value={supportReference}
            onChange={(event) =>
              setSupportReference(event.target.value as "breakout" | "ma_fast" | "either" | "both")
            }
            className="w-full rounded-xl border border-border bg-panelMuted px-3 py-2 text-sm text-text outline-none"
          >
            <option value="breakout">breakout</option>
            <option value="ma_fast">ma_fast</option>
            <option value="either">either</option>
            <option value="both">both</option>
          </select>
        </Field>
        <Field label="Support tolerance pct">
          <Input
            value={supportTolerancePct}
            onChange={(event) => setSupportTolerancePct(event.target.value)}
          />
        </Field>
        <Field label="Order type">
          <select
            value={orderType}
            onChange={(event) => setOrderType(event.target.value as "market" | "limit" | "stop_limit")}
            className="w-full rounded-xl border border-border bg-panelMuted px-3 py-2 text-sm text-text outline-none"
          >
            <option value="market">market</option>
            <option value="limit">limit</option>
            <option value="stop_limit">stop_limit</option>
          </select>
        </Field>
        <label className="flex items-center justify-between rounded-2xl border border-border/70 bg-panelMuted/50 px-4 py-3 text-sm text-text">
          <span>AUTO_BUY_ENABLED</span>
          <input
            type="checkbox"
            checked={autoBuyEnabled}
            onChange={(event) => setAutoBuyEnabled(event.target.checked)}
          />
        </label>
        <label className="flex items-center justify-between rounded-2xl border border-border/70 bg-panelMuted/50 px-4 py-3 text-sm text-text">
          <span>PAPER_TRADING</span>
          <input
            type="checkbox"
            checked={paperTrading}
            onChange={(event) => setPaperTrading(event.target.checked)}
          />
        </label>
        <Button
          onClick={() =>
            onSave({
              scanner: { refresh_seconds: Number(refreshSeconds) || 45 },
              strategy: {
                trigger_timeframe: triggerTimeframe,
                breakout_volume_multiplier: Number(breakoutVolumeMultiplier) || 2.0,
                support_reference: supportReference,
                support_tolerance_pct: Number(supportTolerancePct) || 0.02
              },
              execution: {
                auto_buy_enabled: autoBuyEnabled,
                paper_trading: paperTrading,
                order_type: orderType
              }
            })
          }
          disabled={saving}
          className="w-full gap-2"
        >
          <Save className="h-4 w-4" />
          {saving ? "저장 중..." : "런타임 설정 저장"}
        </Button>
      </div>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="text-xs text-muted">{label}</div>
      {children}
    </div>
  );
}
