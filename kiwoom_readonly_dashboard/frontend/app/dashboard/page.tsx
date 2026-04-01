"use client";

import type { Dispatch, SetStateAction } from "react";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";

import { AccountSummary } from "@/components/account-summary";
import { AdminSettingsPanel } from "@/components/admin-settings-panel";
import { BlockedPanel } from "@/components/blocked-panel";
import { High52CandidatesPanel } from "@/components/high52-candidates-panel";
import { HoldingsTable } from "@/components/holdings-table";
import { NewsPanel } from "@/components/news-panel";
import { OrderLogPanel } from "@/components/order-log-panel";
import { OrderbookPanel } from "@/components/orderbook-panel";
import { SignalQueuePanel } from "@/components/signal-queue-panel";
import { StatusBar } from "@/components/status-bar";
import { StockHeader } from "@/components/stock-header";
import { StockSearch } from "@/components/stock-search";
import { StrategyChartPanel } from "@/components/strategy-chart-panel";
import { StrategyExplainer } from "@/components/strategy-explainer";
import { StrategyParamsPanel } from "@/components/strategy-params-panel";
import { WatchingPanel } from "@/components/watching-panel";
import { Watchlist } from "@/components/watchlist";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { dashboardApi } from "@/lib/api";
import { useDashboardWs } from "@/lib/use-dashboard-ws";
import type {
  AccountSummary as AccountSummaryType,
  HoldingItem,
  NewsResponse,
  OrderbookSnapshot,
  RealtimeEnvelope,
  StatusPanel,
  StockDetailResponse,
  StockSearchItem,
  StrategyDashboardSnapshot,
  StrategySymbolDetail
} from "@/types/dashboard";

const DEFAULT_SYMBOL = "005930";
const WATCHLIST_KEY = "kiwoom-dashboard-watchlist";

export default function DashboardPage() {
  const [summary, setSummary] = useState<AccountSummaryType | null>(null);
  const [holdings, setHoldings] = useState<HoldingItem[]>([]);
  const [status, setStatus] = useState<StatusPanel | null>(null);
  const [detail, setDetail] = useState<StockDetailResponse | null>(null);
  const [news, setNews] = useState<NewsResponse | null>(null);
  const [strategySnapshot, setStrategySnapshot] = useState<StrategyDashboardSnapshot | null>(null);
  const [strategyDetail, setStrategyDetail] = useState<StrategySymbolDetail | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<StockSearchItem[]>([]);
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [loadingSelection, setLoadingSelection] = useState(false);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [executingSignalId, setExecutingSignalId] = useState<string | null>(null);
  const [savingAdmin, setSavingAdmin] = useState(false);
  const { events, connected: realtimeConnected } = useDashboardWs(selectedSymbol);

  const debouncedQuery = useDebouncedValue(searchQuery, 250);
  const currentCompanyName = detail?.quote.name ?? news?.company_name ?? "";

  useEffect(() => {
    const saved = window.localStorage.getItem(WATCHLIST_KEY);
    if (saved) {
      try {
        setWatchlist(JSON.parse(saved) as string[]);
      } catch {
        window.localStorage.removeItem(WATCHLIST_KEY);
      }
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
  }, [watchlist]);

  useEffect(() => {
    let active = true;

    const loadOverview = async () => {
      try {
        const [summaryResponse, holdingsResponse, statusResponse, scannerResponse] = await Promise.all([
          dashboardApi.getSummary(),
          dashboardApi.getHoldings(),
          dashboardApi.getStatus(),
          dashboardApi.getScannerOverview()
        ]);
        if (!active) return;
        setSummary(summaryResponse);
        setHoldings(holdingsResponse.items);
        setStatus(statusResponse);
        setStrategySnapshot(scannerResponse);
        setSelectedSymbol(
          (current) =>
            current ??
            holdingsResponse.items[0]?.symbol ??
            scannerResponse.candidates[0]?.symbol ??
            DEFAULT_SYMBOL
        );
        setPageError(null);
      } catch (error) {
        if (!active) return;
        setPageError(error instanceof Error ? error.message : "대시보드 개요를 불러오지 못했습니다.");
      } finally {
        if (active) setLoadingOverview(false);
      }
    };

    void loadOverview();
    const timer = window.setInterval(() => {
      void loadOverview();
    }, 30000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!selectedSymbol) {
      return;
    }

    let active = true;
    setLoadingSelection(true);

    const loadSelection = async () => {
      try {
        const [detailResponse, newsResponse, strategyResponse] = await Promise.all([
          dashboardApi.getStockDetail(selectedSymbol),
          dashboardApi.getNews(selectedSymbol),
          dashboardApi.getStrategyDetail(selectedSymbol)
        ]);
        if (!active) return;
        setDetail(detailResponse);
        setNews(newsResponse);
        setStrategyDetail(strategyResponse);
        setPageError(null);
      } catch (error) {
        if (!active) return;
        setPageError(error instanceof Error ? error.message : "선택 종목 상세를 불러오지 못했습니다.");
      } finally {
        if (active) setLoadingSelection(false);
      }
    };

    void loadSelection();
    return () => {
      active = false;
    };
  }, [selectedSymbol]);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setSearchResults([]);
      return;
    }

    let active = true;
    setLoadingSearch(true);

    const loadSearch = async () => {
      try {
        const response = await dashboardApi.searchStocks(debouncedQuery);
        if (!active) return;
        setSearchResults(response.items);
      } catch {
        if (!active) return;
        setSearchResults([]);
      } finally {
        if (active) setLoadingSearch(false);
      }
    };

    void loadSearch();
    return () => {
      active = false;
    };
  }, [debouncedQuery]);

  useEffect(() => {
    if (!events.length) return;
    const latest = events[events.length - 1];
    applyRealtimeEvent(latest, setDetail, setStatus);
  }, [events]);

  const orderbook = useMemo<OrderbookSnapshot | null>(
    () => detail?.orderbook ?? null,
    [detail]
  );

  const executionConfig = strategySnapshot?.config.execution;

  const handleSignalExecute = async (signalId: string) => {
    setExecutingSignalId(signalId);
    try {
      await dashboardApi.executeSignal(signalId);
      const [overview, refreshedDetail] = await Promise.all([
        dashboardApi.getScannerOverview(),
        selectedSymbol ? dashboardApi.getStrategyDetail(selectedSymbol) : Promise.resolve(null)
      ]);
      setStrategySnapshot(overview);
      if (refreshedDetail) {
        setStrategyDetail(refreshedDetail);
      }
      setPageError(null);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "모의주문 실행에 실패했습니다.");
    } finally {
      setExecutingSignalId(null);
    }
  };

  const handleAdminSave = async (payload: Record<string, unknown>) => {
    setSavingAdmin(true);
    try {
      await dashboardApi.updateStrategyConfig(payload);
      const overview = await dashboardApi.refreshScanner();
      setStrategySnapshot(overview);
      if (selectedSymbol) {
        setStrategyDetail(await dashboardApi.getStrategyDetail(selectedSymbol));
      }
      setPageError(null);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "전략 설정 저장에 실패했습니다.");
    } finally {
      setSavingAdmin(false);
    }
  };

  return (
    <main className="min-h-screen px-5 py-6 xl:px-8">
      <div className="mx-auto flex max-w-[1680px] flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-accent">Kiwoom Strategy Dashboard</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-text">
              52주 신고가 눌림목 매수 시스템
            </h1>
            <p className="mt-2 text-sm text-muted">
              기본값은 조회 + 신호생성 + 모의주문만 허용합니다. 실주문은 별도 feature flag가 꺼져 있으면 절대 실행되지 않습니다.
            </p>
          </div>
          <Button onClick={() => window.location.reload()} className="gap-2">
            <RefreshCcw className="h-4 w-4" />
            새로고침
          </Button>
        </div>

        <Card className="border-warning/30 bg-warning/10 p-4">
          <p className="text-sm text-yellow-100">
            SAFETY: {executionConfig?.paper_trading ? "PAPER_TRADING=true" : "PAPER_TRADING=false"} /{" "}
            {executionConfig?.auto_buy_enabled ? "AUTO_BUY_ENABLED=true" : "AUTO_BUY_ENABLED=false"} /{" "}
            {executionConfig?.use_mock_only ? "USE_MOCK_ONLY=true" : "USE_MOCK_ONLY=false"} /{" "}
            {executionConfig?.real_order_enabled ? "REAL_ORDER_ENABLED=true" : "REAL_ORDER_ENABLED=false"}
          </p>
        </Card>

        <AccountSummary summary={summary} loading={loadingOverview} />

        {pageError ? (
          <Card className="border-danger/30 bg-danger/10 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-danger" />
              <div>
                <div className="text-sm font-semibold text-red-100">오류</div>
                <p className="mt-1 text-sm text-red-200/85">{pageError}</p>
              </div>
            </div>
          </Card>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)_420px]">
          <div className="space-y-6">
            <StockSearch
              query={searchQuery}
              onQueryChange={setSearchQuery}
              results={searchResults}
              loading={loadingSearch}
              onSelect={(item) => {
                setSelectedSymbol(item.symbol);
                setSearchQuery("");
                setSearchResults([]);
              }}
            />
            <Watchlist
              items={watchlist}
              selectedSymbol={selectedSymbol}
              onSelect={setSelectedSymbol}
              onRemove={(symbol) =>
                setWatchlist((current) => current.filter((item) => item !== symbol))
              }
            />
            <High52CandidatesPanel
              items={strategySnapshot?.candidates ?? []}
              source={strategySnapshot?.scanner_source ?? null}
              selectedSymbol={selectedSymbol}
              onSelect={setSelectedSymbol}
            />
            <HoldingsTable
              items={holdings}
              loading={loadingOverview}
              selectedSymbol={selectedSymbol}
              onSelect={setSelectedSymbol}
            />
            <WatchingPanel items={strategySnapshot?.watching ?? []} onSelect={setSelectedSymbol} />
          </div>

          <div className="space-y-6">
            <StockHeader
              detail={detail}
              loading={loadingSelection}
              onAddWatchlist={() => {
                if (!selectedSymbol) return;
                setWatchlist((current) =>
                  current.includes(selectedSymbol) ? current : [selectedSymbol, ...current]
                );
              }}
            />
            <StrategyChartPanel detail={strategyDetail} loading={loadingSelection} />
            <StrategyExplainer detail={strategyDetail} loading={loadingSelection} />
            <OrderbookPanel orderbook={orderbook} loading={loadingSelection} />
          </div>

          <div className="space-y-6">
            <SignalQueuePanel
              items={strategySnapshot?.queued_signals ?? []}
              executionConfig={
                executionConfig ?? {
                  paper_trading: true,
                  auto_buy_enabled: false,
                  use_mock_only: true,
                  real_order_enabled: false,
                  order_type: "market",
                  slippage_bps: 10,
                  max_retry_count: 1,
                  fill_poll_seconds: 2,
                  manual_signal_execution: true
                }
              }
              onExecute={handleSignalExecute}
              executingSignalId={executingSignalId}
              onSelectSymbol={setSelectedSymbol}
            />
            <BlockedPanel items={strategySnapshot?.blocked ?? []} />
            <OrderLogPanel
              orders={strategySnapshot?.orders ?? []}
              fills={strategySnapshot?.fills ?? []}
            />
            <StrategyParamsPanel snapshot={strategySnapshot} />
            <AdminSettingsPanel
              config={strategySnapshot?.config ?? null}
              onSave={handleAdminSave}
              saving={savingAdmin}
            />
            <NewsPanel
              items={news?.items ?? []}
              provider={news?.provider ?? null}
              loading={loadingSelection}
              companyName={currentCompanyName}
            />
            <StatusBar status={status} realtimeConnected={realtimeConnected} />
          </div>
        </div>
      </div>
    </main>
  );
}

function useDebouncedValue<T>(value: T, delay: number) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

function applyRealtimeEvent(
  event: RealtimeEnvelope,
  setDetail: Dispatch<SetStateAction<StockDetailResponse | null>>,
  setStatus: Dispatch<SetStateAction<StatusPanel | null>>
) {
  if (event.channel === "quote") {
    setDetail((current) => {
      if (!current || !event.symbol || current.quote.symbol !== event.symbol) return current;
      return {
        ...current,
        quote: {
          ...current.quote,
          current_price: numberOrFallback(event.payload.current_price, current.quote.current_price),
          diff_from_previous_close: numberOrFallback(
            event.payload.diff_from_previous_close,
            current.quote.diff_from_previous_close
          ),
          change_rate: numberOrFallback(event.payload.change_rate, current.quote.change_rate),
          volume: numberOrFallback(event.payload.accumulated_volume, current.quote.volume),
          open_price: numberOrFallback(event.payload.open_price, current.quote.open_price),
          high_price: numberOrFallback(event.payload.high_price, current.quote.high_price),
          low_price: numberOrFallback(event.payload.low_price, current.quote.low_price),
          best_ask: numberOrFallback(event.payload.best_ask, current.quote.best_ask ?? 0),
          best_bid: numberOrFallback(event.payload.best_bid, current.quote.best_bid ?? 0),
          updated_at: event.updated_at
        }
      };
    });
  }

  if (event.channel === "orderbook") {
    setDetail((current) => {
      if (!current || !event.symbol || current.quote.symbol !== event.symbol) return current;
      return {
        ...current,
        orderbook: {
          symbol: event.symbol,
          asks: Array.isArray(event.payload.asks) ? (event.payload.asks as OrderbookSnapshot["asks"]) : [],
          bids: Array.isArray(event.payload.bids) ? (event.payload.bids as OrderbookSnapshot["bids"]) : [],
          total_ask_quantity: numberOrNull(event.payload.total_ask_quantity),
          total_bid_quantity: numberOrNull(event.payload.total_bid_quantity),
          timestamp: stringOrNull(event.payload.timestamp),
          updated_at: event.updated_at
        }
      };
    });
  }

  if (event.channel === "market_status") {
    setDetail((current) => {
      if (!current) return current;
      return {
        ...current,
        quote: {
          ...current.quote,
          market_phase: stringOrNull(event.payload.label) ?? current.quote.market_phase,
          updated_at: event.updated_at
        }
      };
    });
  }

  if (event.channel === "status" || event.channel === "market_status") {
    setStatus((current) =>
      current
        ? {
            ...current,
            kiwoom_websocket: {
              ...current.kiwoom_websocket,
              connected: event.channel === "market_status" || current.kiwoom_websocket.connected,
              status: event.channel === "market_status" ? "connected" : current.kiwoom_websocket.status,
              detail: stringOrNull(event.payload.detail) ?? stringOrNull(event.payload.label),
              last_updated_at: event.updated_at
            },
            last_refresh_at: event.updated_at
          }
        : current
    );
  }
}

function numberOrFallback(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function numberOrNull(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function stringOrNull(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}
