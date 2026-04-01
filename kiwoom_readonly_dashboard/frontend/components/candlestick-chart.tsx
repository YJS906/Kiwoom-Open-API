"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  type HistogramData,
  type IChartApi,
  type Time,
  createChart
} from "lightweight-charts";

import type { ChartResponse } from "@/types/dashboard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const ranges = ["1m", "3m", "6m", "1y"] as const;

export function CandlestickChart({
  chart,
  loading,
  range,
  interval,
  onRangeChange,
  onIntervalChange
}: {
  chart: ChartResponse | null;
  loading: boolean;
  range: string;
  interval: "day" | "minute";
  onRangeChange: (value: "1m" | "3m" | "6m" | "1y") => void;
  onIntervalChange: (value: "day" | "minute") => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || !chart?.bars.length) {
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
      height: 440,
      rightPriceScale: {
        borderColor: "rgba(148, 163, 184, 0.16)"
      },
      timeScale: {
        borderColor: "rgba(148, 163, 184, 0.16)"
      },
      crosshair: {
        vertLine: { color: "rgba(59, 130, 246, 0.45)" },
        horzLine: { color: "rgba(59, 130, 246, 0.25)" }
      }
    });

    chartRef.current = chartApi;
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

    const candleData = chart.bars.map((bar) => ({
      time: toChartTime(bar.time),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close
    }));
    const volumeData = chart.bars.map(
      (bar): HistogramData<Time> => ({
        time: toChartTime(bar.time),
        value: bar.volume,
        color: bar.close >= bar.open ? "rgba(34,197,94,0.55)" : "rgba(239,68,68,0.55)"
      })
    );

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);
    chartApi.timeScale().fitContent();

    const handleResize = () => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chartApi.remove();
      chartRef.current = null;
    };
  }, [chart]);

  return (
    <Card className="p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-text">차트</h2>
          <p className="mt-1 text-xs text-muted">일봉 기본, 분봉 탭 지원</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="flex gap-2 rounded-xl border border-border/70 bg-panelMuted/60 p-1">
            <Button
              className={interval === "day" ? "bg-accent/20 text-text" : "border-transparent"}
              onClick={() => onIntervalChange("day")}
            >
              일봉
            </Button>
            <Button
              className={interval === "minute" ? "bg-accent/20 text-text" : "border-transparent"}
              onClick={() => onIntervalChange("minute")}
            >
              분봉
            </Button>
          </div>
          <div className="flex gap-2 rounded-xl border border-border/70 bg-panelMuted/60 p-1">
            {ranges.map((item) => (
              <Button
                key={item}
                className={range === item ? "bg-accent/20 text-text" : "border-transparent"}
                onClick={() => onRangeChange(item)}
              >
                {item}
              </Button>
            ))}
          </div>
        </div>
      </div>
      {loading ? (
        <Skeleton className="h-[440px] w-full rounded-2xl" />
      ) : chart?.bars.length ? (
        <div ref={containerRef} className="w-full overflow-hidden rounded-2xl" />
      ) : (
        <div className="flex h-[440px] items-center justify-center rounded-2xl border border-dashed border-border/70 text-sm text-muted">
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
