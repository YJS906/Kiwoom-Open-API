"use client";

import { Search } from "lucide-react";

import type { StockSearchItem } from "@/types/dashboard";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export function StockSearch({
  query,
  onQueryChange,
  results,
  loading,
  onSelect
}: {
  query: string;
  onQueryChange: (value: string) => void;
  results: StockSearchItem[];
  loading: boolean;
  onSelect: (item: StockSearchItem) => void;
}) {
  return (
    <Card className="relative p-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="종목명 또는 종목코드 검색"
          className="pl-10"
        />
      </div>
      {query.trim() ? (
        <div className="mt-3 max-h-72 overflow-auto rounded-xl border border-border/60 bg-panelMuted/60">
          {loading ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          ) : results.length === 0 ? (
            <div className="p-4 text-sm text-muted">검색 결과가 없습니다.</div>
          ) : (
            <ul className="divide-y divide-border/60">
              {results.map((item) => (
                <li key={item.symbol}>
                  <button
                    type="button"
                    onClick={() => onSelect(item)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-accent/10"
                  >
                    <div>
                      <div className="font-medium text-text">{item.name}</div>
                      <div className="text-xs text-muted">
                        {item.symbol} · {item.market_name}
                      </div>
                    </div>
                    <div className="text-sm text-muted">
                      {item.last_price ? item.last_price.toLocaleString("ko-KR") : "-"}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </Card>
  );
}
