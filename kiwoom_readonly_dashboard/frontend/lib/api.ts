import type {
  AccountSummary,
  ChartResponse,
  FillEvent,
  HoldingsResponse,
  NewsResponse,
  OrderIntent,
  ReplayResponse,
  StatusPanel,
  StrategyDashboardSnapshot,
  StrategySymbolDetail,
  TradingConfig,
  StockDetailResponse,
  StockSearchResponse
} from "@/types/dashboard";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: `Request failed with ${response.status}` }));
    throw new Error(payload.detail ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const dashboardApi = {
  getStatus: () => requestJson<StatusPanel>("/api/health"),
  getSummary: () => requestJson<AccountSummary>("/api/account/summary"),
  getHoldings: () => requestJson<HoldingsResponse>("/api/account/holdings"),
  searchStocks: (query: string) =>
    requestJson<StockSearchResponse>(`/api/stocks/search?q=${encodeURIComponent(query)}`),
  getStockDetail: (symbol: string) =>
    requestJson<StockDetailResponse>(`/api/stocks/${symbol}`),
  getChart: (symbol: string, range: string, interval: string) =>
    requestJson<ChartResponse>(
      `/api/chart/${symbol}?range=${encodeURIComponent(range)}&interval=${encodeURIComponent(interval)}`
    ),
  getNews: (symbol: string) => requestJson<NewsResponse>(`/api/news/${symbol}`),
  getScannerOverview: () => requestJson<StrategyDashboardSnapshot>("/api/scanner/overview"),
  refreshScanner: () =>
    requestJson<StrategyDashboardSnapshot>("/api/scanner/refresh"),
  getStrategyDetail: (symbol: string) =>
    requestJson<StrategySymbolDetail>(`/api/strategy/detail/${symbol}`),
  getStrategyConfig: () => requestJson<TradingConfig>("/api/strategy/config"),
  updateStrategyConfig: (payload: Record<string, unknown>) =>
    requestJson<TradingConfig>("/api/strategy/config", {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  getReplay: (symbol: string) =>
    requestJson<ReplayResponse>(`/api/signals/replay/${symbol}`),
  getOrders: () => requestJson<OrderIntent[]>("/api/orders"),
  getFills: () => requestJson<FillEvent[]>("/api/orders/fills"),
  executeSignal: (signalId: string) =>
    requestJson<Record<string, unknown>>(`/api/orders/execute/${encodeURIComponent(signalId)}`, {
      method: "POST"
    })
};

export { API_BASE_URL };
