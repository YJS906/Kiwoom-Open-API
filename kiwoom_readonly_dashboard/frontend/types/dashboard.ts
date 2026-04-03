export type ConnectionState = {
  connected: boolean;
  status: string;
  last_updated_at: string | null;
  detail: string | null;
};

export type StatusPanel = {
  kiwoom_rest: ConnectionState;
  kiwoom_websocket: ConnectionState;
  news_provider: ConnectionState;
  strategy_engine?: ConnectionState | null;
  last_refresh_at: string | null;
  recent_errors: string[];
};

export type AccountSummary = {
  total_evaluation_amount: number;
  total_profit_loss: number;
  total_profit_rate: number;
  holdings_count: number;
  deposit: number;
  orderable_amount: number;
  estimated_assets: number;
  updated_at: string;
};

export type HoldingItem = {
  symbol: string;
  name: string;
  quantity: number;
  available_quantity: number;
  average_price: number;
  current_price: number;
  evaluation_profit_loss: number;
  profit_rate: number;
  market_name?: string | null;
};

export type HoldingsResponse = {
  items: HoldingItem[];
  updated_at: string;
};

export type StockSearchItem = {
  symbol: string;
  name: string;
  market_code: string;
  market_name: string;
  last_price?: number | null;
};

export type StockSearchResponse = {
  items: StockSearchItem[];
  updated_at: string;
};

export type StockQuote = {
  symbol: string;
  name: string;
  market_name?: string | null;
  current_price: number;
  previous_close: number;
  diff_from_previous_close: number;
  change_rate: number;
  volume: number;
  open_price: number;
  high_price: number;
  low_price: number;
  best_ask?: number | null;
  best_bid?: number | null;
  market_phase?: string | null;
  updated_at: string;
};

export type OrderbookLevel = {
  price: number;
  quantity: number;
  delta?: number | null;
};

export type OrderbookSnapshot = {
  symbol: string;
  asks: OrderbookLevel[];
  bids: OrderbookLevel[];
  total_ask_quantity?: number | null;
  total_bid_quantity?: number | null;
  timestamp?: string | null;
  updated_at: string;
};

export type StockDetailResponse = {
  quote: StockQuote;
  orderbook?: OrderbookSnapshot | null;
};

export type RealtimeHigh52Item = {
  symbol: string;
  name: string;
  current_price: number;
  diff_from_previous_close: number;
  change_rate: number;
  volume: number;
  best_ask?: number | null;
  best_bid?: number | null;
  high_price?: number | null;
  low_price?: number | null;
  market_name?: string | null;
};

export type RealtimeHigh52Response = {
  status: "ok" | "unavailable" | "error";
  source: string;
  environment: "mock" | "production";
  reason?: string | null;
  items: RealtimeHigh52Item[];
  updated_at: string;
};

export type ChartBar = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type ChartResponse = {
  symbol: string;
  interval: "day" | "minute";
  range_label: string;
  bars: ChartBar[];
  updated_at: string;
};

export type NewsItem = {
  title: string;
  source: string;
  published_at?: string | null;
  url: string;
  summary?: string | null;
  provider: string;
};

export type NewsResponse = {
  symbol: string;
  company_name: string;
  provider: string;
  items: NewsItem[];
  updated_at: string;
};

export type RealtimeEnvelope = {
  channel: "quote" | "orderbook" | "market_status" | "status" | "error";
  symbol?: string | null;
  payload: Record<string, unknown>;
  updated_at: string;
};

export type CandidateState =
  | "new"
  | "watching"
  | "signal_ready"
  | "ordered"
  | "exited"
  | "blocked";

export type SignalStatus =
  | "queued"
  | "blocked"
  | "ordered"
  | "filled"
  | "expired"
  | "cancelled"
  | "closed";

export type StrategyOrderType = "market" | "limit" | "stop_limit";
export type StrategyTimeframe = "daily" | "weekly" | "60m" | "15m" | "5m";

export type ScannerConfig = {
  condition_name: string;
  refresh_seconds: number;
  candidate_ttl_minutes: number;
  min_daily_history: number;
  fallback_symbols: string[];
};

export type StrategyConfig = {
  strategy_profile: "high52_pullback" | "high52_breakout" | "box_breakout";
  recent_breakout_days: number;
  daily_ma_fast: number;
  daily_ma_slow: number;
  breakout_volume_multiplier: number;
  breakout_volume_lookback_days: number;
  pullback_min_ratio: number;
  pullback_max_ratio: number;
  volume_dryup_ratio: number;
  support_reference: "breakout" | "ma_fast" | "either" | "both";
  support_tolerance_pct: number;
  trigger_timeframe: "15m" | "5m";
  use_vwap: boolean;
  require_bullish_reversal_candle: boolean;
  min_daily_bars: number;
  min_intraday_bars: number;
  breakout_lookback_bars_60m: number;
  rally_window_bars_60m: number;
  breakout_entry_buffer_pct: number;
  box_window_days: number;
  box_max_range_pct: number;
  box_breakout_volume_multiplier: number;
  box_breakout_buffer_pct: number;
};

export type RiskConfig = {
  buy_cash_pct_of_remaining: number;
  max_position_pct: number;
  max_positions: number;
  max_daily_new_entries: number;
  max_daily_loss_krw: number;
  reentry_cooldown_minutes: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  no_new_entry_after: string;
  block_reentry_after_stop: boolean;
  block_high_volatility: boolean;
  max_intraday_change_pct: number;
  exclude_trading_halt: boolean;
  exclude_admin_issue: boolean;
  exclude_etf_etn: boolean;
};

export type ExecutionConfig = {
  paper_trading: boolean;
  auto_buy_enabled: boolean;
  use_mock_only: boolean;
  mock_order_enabled: boolean;
  real_order_enabled: boolean;
  order_type: StrategyOrderType;
  slippage_bps: number;
  max_retry_count: number;
  fill_poll_seconds: number;
  manual_signal_execution: boolean;
};

export type SessionConfig = {
  timezone: string;
  market_open_time: string;
  market_close_time: string;
  manage_overnight_positions_on_open: boolean;
};

export type AdminConfig = {
  enable_runtime_overrides: boolean;
  replay_default_days: number;
};

export type TradingConfig = {
  scanner: ScannerConfig;
  strategy: StrategyConfig;
  risk: RiskConfig;
  execution: ExecutionConfig;
  session: SessionConfig;
  admin: AdminConfig;
};

export type PriceLevel = {
  label: string;
  price: number;
  kind: "entry" | "stop" | "target" | "breakout" | "support" | "resistance";
};

export type TradeBar = {
  timeframe: StrategyTimeframe;
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type CandidateStock = {
  symbol: string;
  name: string;
  state: CandidateState;
  source: string;
  condition_name?: string | null;
  condition_seq?: string | null;
  breakout_date?: string | null;
  breakout_price?: number | null;
  last_price?: number | null;
  change_rate?: number | null;
  market_name?: string | null;
  note?: string | null;
  blocked_reason?: string | null;
  detected_at: string;
  updated_at: string;
};

export type RiskDecision = {
  allowed: boolean;
  reasons: string[];
  blocked_category?: string | null;
  remaining_cash_krw: number;
  suggested_order_cash_krw: number;
  quantity: number;
  checked_at: string;
};

export type StrategyDecision = {
  symbol: string;
  passed: boolean;
  stage:
    | "insufficient_data"
    | "daily_filter"
    | "pullback_filter"
    | "trigger"
    | "buy_signal"
    | "exit_signal"
    | "hold";
  summary: string;
  reasons: string[];
  entry_timeframe?: StrategyTimeframe | null;
  entry_price?: number | null;
  stop_price?: number | null;
  target_price?: number | null;
  breakout_price?: number | null;
  pullback_ratio?: number | null;
  rally_volume_avg?: number | null;
  pullback_volume_avg?: number | null;
  vwap?: number | null;
  annotations: PriceLevel[];
  metrics: Record<string, unknown>;
  generated_at: string;
};

export type SignalEvent = {
  id: string;
  symbol: string;
  name: string;
  signal_type: "entry" | "exit";
  status: SignalStatus;
  candidate_state: CandidateState;
  trigger_timeframe?: StrategyTimeframe | null;
  decision: StrategyDecision;
  risk?: RiskDecision | null;
  explanation: string;
  created_at: string;
  updated_at: string;
  order_intent_id?: string | null;
};

export type OrderIntent = {
  id: string;
  signal_id: string;
  symbol: string;
  name: string;
  side: "buy" | "sell";
  quantity: number;
  order_type: StrategyOrderType;
  desired_price?: number | null;
  trigger_price?: number | null;
  stop_price?: number | null;
  target_price?: number | null;
  paper: boolean;
  state: "queued" | "submitted" | "filled" | "rejected" | "cancelled";
  reason?: string | null;
  created_at: string;
  updated_at: string;
};

export type FillEvent = {
  id: string;
  order_intent_id: string;
  symbol: string;
  name: string;
  side: "buy" | "sell";
  price: number;
  quantity: number;
  fill_value_krw: number;
  paper: boolean;
  reason?: string | null;
  filled_at: string;
};

export type PositionState = {
  symbol: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value_krw: number;
  unrealized_pnl_krw: number;
  realized_pnl_krw: number;
  stop_price?: number | null;
  target_price?: number | null;
  source: "paper" | "account";
  opened_at: string;
  last_updated_at: string;
  closed_at?: string | null;
};

export type StrategySessionState = {
  trade_date: string;
  market_open: boolean;
  can_enter_new_positions: boolean;
  paper_cash_balance_krw: number;
  actual_available_cash_krw: number;
  actual_holdings_count: number;
  daily_new_entries: number;
  daily_loss_krw: number;
  halted: boolean;
  halt_reason?: string | null;
  recent_stop_loss_symbols: string[];
  cooldown_until: Record<string, string>;
  pending_overnight_symbols: string[];
  last_open_management_date?: string | null;
  last_scan_at?: string | null;
  last_signal_at?: string | null;
  last_order_at?: string | null;
  last_error?: string | null;
  updated_at: string;
};

export type StrategyStatus = {
  connected: boolean;
  status: string;
  last_updated_at?: string | null;
  detail?: string | null;
};

export type StrategyDashboardSnapshot = {
  candidates: CandidateStock[];
  watching: CandidateStock[];
  signal_ready: CandidateStock[];
  blocked: CandidateStock[];
  queued_signals: SignalEvent[];
  orders: OrderIntent[];
  fills: FillEvent[];
  positions: PositionState[];
  session: StrategySessionState;
  config: TradingConfig;
  status: StrategyStatus;
  scanner_source: string;
  updated_at: string;
};

export type StrategySymbolDetail = {
  symbol: string;
  name: string;
  candidate?: CandidateStock | null;
  decision?: StrategyDecision | null;
  charts: Record<string, TradeBar[]>;
  levels: PriceLevel[];
  explanation_cards: string[];
  updated_at: string;
};

export type StrategyChartSeries = {
  symbol: string;
  timeframe: StrategyTimeframe;
  bars: TradeBar[];
  updated_at: string;
};

export type ReplayPoint = {
  time: string;
  close: number;
  action: "hold" | "entry_ready" | "buy_signal" | "blocked";
  summary: string;
};

export type ReplayResponse = {
  symbol: string;
  timeframe: StrategyTimeframe;
  points: ReplayPoint[];
  decision?: StrategyDecision | null;
  updated_at: string;
};
