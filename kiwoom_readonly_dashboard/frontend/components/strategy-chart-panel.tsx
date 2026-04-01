"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ColorType,
  type HistogramData,
  type IChartApi,
  type IPriceLine,
  type Time,
  createChart
} from "lightweight-charts";

import type { StrategySymbolDetail, StrategyTimeframe, TradeBar } from "@/types/dashboard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const TIMEFRAMES: StrategyTimeframe[] = ["daily", "60m", "15m", "5m"];

export function StrategyChartPanel({
  detail,
  loading
}: {
  detail: StrategySymbolDetail | null;
  loading: boolean;
}) {
  const [timeframe, setTimeframe] = useState<StrategyTimeframe>("daily");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  const bars = useMemo<TradeBar[]>(() => detail?.charts?.[timeframe] ?? [], [detail, timeframe]);

  useEffect(() => {
    if (!containerRef.current || !bars.length) {
      return;
    }

    const chartApi = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9fb0c7"
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.08)" },
        horzLines: { color: "rgba(148, 163, 184, 0.08)" }
      },
      width: containerRef.current.clientWidth,
      height: 420,
      rightPriceScale: {
        borderColor: "rgba(148, 163, 184, 0.16)"
      },
      timeScale: {
        borderColor: "rgba(148, 163, 184, 0.16)"
      }
    });

    const candleSeries = chartApi.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444"
    });
    const volumeSeries = chartApi.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
      color: "#3b82f6"
    });
    chartApi.priceScale("").applyOptions({
      scaleMargins: {
        top: 0.75,
        bottom: 0
      }
    });

    candleSeries.setData(
      bars.map((bar) => ({
        time: toChartTime(bar.time),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close
      }))
    );
    volumeSeries.setData(
      bars.map(
        (bar): HistogramData<Time> => ({
          time: toChartTime(bar.time),
          value: bar.volume,
          color: bar.close >= bar.open ? "rgba(34,197,94,0.55)" : "rgba(239,68,68,0.55)"
        })
      )
    );

    priceLinesRef.current.forEach((line) => candleSeries.removePriceLine(line));
    priceLinesRef.current = (detail?.levels ?? []).map((level) =>
      candleSeries.createPriceLine({
        price: level.price,
        color:
          level.kind === "entry"
            ? "#3b82f6"
            : level.kind === "stop"
              ? "#ef4444"
              : level.kind === "target"
                ? "#22c55e"
                : "#f59e0b",
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: level.label
      })
    );

    chartApi.timeScale().fitContent();
    chartRef.current = chartApi;

    const handleResize = () => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chartApi.remove();
      chartRef.current = null;
      priceLinesRef.current = [];
    };
  }, [bars, detail]);

  return (
    <Card className="p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-text">전략 멀티타임프레임 차트</h2>
          <p className="mt-1 text-xs text-muted">일봉, 60분봉, 15분봉, 5분봉을 한 패널에서 전환합니다.</p>
        </div>
        <div className="flex gap-2 rounded-xl border border-border/70 bg-panelMuted/60 p-1">
          {TIMEFRAMES.map((item) => (
            <Button
              key={item}
              className={timeframe === item ? "bg-accent/20 text-text" : "border-transparent"}
              onClick={() => setTimeframe(item)}
            >
              {item}
            </Button>
          ))}
        </div>
      </div>
      {loading ? (
        <Skeleton className="h-[420px] w-full rounded-2xl" />
      ) : bars.length ? (
        <div className="space-y-4">
          <div ref={containerRef} className="w-full overflow-hidden rounded-2xl" />
          <div className="flex flex-wrap gap-2 text-xs text-muted">
            {(detail?.levels ?? []).map((level) => (
              <div key={`${level.kind}-${level.label}`} className="rounded-full border border-border/70 bg-panelMuted/60 px-3 py-1">
                {level.label}: {level.price.toLocaleString("ko-KR")}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex h-[420px] items-center justify-center rounded-2xl border border-dashed border-border/70 text-sm text-muted">
          차트 데이터가 없습니다.
        </div>
      )}
    </Card>
  );
}

function toChartTime(value: string): Time {
  if (value.includes("T")) {
    return Math.floor(new Date(value).getTime() / 1000) as Time;
  }
  const [year, month, day] = value.split("-").map(Number);
  return { year, month, day } as Time;
}

