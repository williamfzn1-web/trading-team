export interface PriceTick {
  price: number;
  change_24h: number;
  volume_24h: number;
  high_24h: number;
  low_24h: number;
}

export interface Analyst {
  id: number;
  name: string;
  strategy: string;
  strategy_description: string;
  avatar_color: string;
  initial_capital: number;
  current_balance: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  pnl_pct: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown: number;
  total_trades: number;
  open_positions: number;
  occupied_margin: number;
  total_equity: number;
}

export interface EquityPoint {
  timestamp: string;
  balance: number;
  unrealized_pnl?: number;
}

export interface GroupMessage {
  id: number;
  analyst_id: number;
  analyst_name: string;
  analyst_color: string;
  strategy: string;
  content: string;
  message_type: string;
  timestamp: string;
}

export interface WSPayload {
  type: string;
  prices: Record<string, PriceTick>;
  accounts: Analyst[];
}

export interface AnalystRiskStatus {
  id: number;
  name: string;
  strategy: string;
  avatar_color: string;
  can_trade: boolean;
  pause_reason: string | null;
  paused_until: string | null;
  consecutive_losses: number;
  size_multiplier: number;
  peak_balance: number;
  current_balance: number;
  drawdown_pct: number;
}

export interface BacktestRun {
  id: number;
  strategy: string;
  primary_symbol: string;
  period_days: number;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  total_trades: number;
  win_rate: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  profit_factor: number;
  avg_win_usdt: number;
  avg_loss_usdt: number;
  initial_capital: number;
  final_capital: number;
  error_msg: string | null;
}

export interface PaperStats {
  total_equity: number;
  total_initial: number;
  total_return_pct: number;
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
}

export interface PaperPosition {
  id: number;
  analyst: string;
  strategy: string;
  symbol: string;
  side: string;
  entry_price: number;
  current_price: number | null;
  quantity: number;
  leverage: number;
  stop_loss: number | null;
  take_profit: number | null;
  unrealized_pnl: number;
  entry_time: string | null;
  notes: string | null;
}

export interface PaperTrade {
  id: number;
  analyst: string;
  strategy: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  leverage: number;
  realized_pnl: number;
  entry_time: string | null;
  exit_time: string | null;
}

export interface WFWindow {
  window: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  train: { return_pct: number; win_rate: number; sharpe: number; max_dd: number; profit_factor: number; trades: number };
  test:  { return_pct: number; win_rate: number; sharpe: number; max_dd: number; profit_factor: number; trades: number };
  consistency: number;
}

export interface WalkForwardRun {
  id: number;
  strategy: string;
  primary_symbol: string;
  train_days: number;
  test_days: number;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  n_windows: number;
  avg_consistency: number;
  error_msg: string | null;
}

export interface OpenPosition {
  id: number;
  analyst_id: number;
  analyst_name: string;
  analyst_color: string;
  strategy: string;
  symbol: string;
  side: string;
  entry_price: number;
  current_price: number;
  quantity: number;
  leverage: number;
  margin: number;
  unrealized_pnl: number;
  stop_loss: number | null;
  take_profit: number | null;
  entry_time: string | null;
}

export interface DailyPnL {
  date: string;
  pnl: number;
  total: number;
}

export interface CorrelationData {
  analysts: { id: number; name: string; strategy: string; color: string }[];
  matrix: number[][];
}

export interface ShadowPair {
  analyst: string;
  symbol: string;
  side: string;
  entry_time: string | null;
  exit_time: string | null;
  live: { id: number; entry_price: number; exit_price: number | null; realized_pnl: number };
  shadow: { id: number; entry_price: number; exit_price: number | null; realized_pnl: number } | null;
  diff: { entry_slippage: number; exit_slippage: number; pnl_diff: number } | null;
}

export interface ShadowSummary {
  pairs?: number;
  message?: string;
  avg_entry_slippage?: number;
  avg_exit_slippage?: number;
  avg_pnl_diff?: number;
  total_pnl_diff?: number;
}

export interface RiskStatus {
  portfolio: {
    total_balance: number;
    peak_balance: number;
    drawdown_pct: number;
    circuit_breaker_active: boolean;
    circuit_breaker_msg: string | null;
    drawdown_limit_pct: number;
  };
  analysts: AnalystRiskStatus[];
  rules: {
    daily_loss_limit_pct: number;
    portfolio_drawdown_limit_pct: number;
    max_same_direction: number;
    consec_reduce_at: number;
    consec_pause_at: number;
    min_balance: number;
  };
}

export interface MCResult {
  run_id: number;
  strategy: string;
  n_sims: number;
  n_trades: number;
  return: { p5: number; p25: number; p50: number; p75: number; p95: number; mean: number };
  max_drawdown: { p50: number; p95: number; worst: number };
  prob_profit_pct: number;
  prob_ruin_pct: number;
  bands: {
    p5: number[];
    p25: number[];
    p50: number[];
    p75: number[];
    p95: number[];
    x_labels: number[];
  };
}
