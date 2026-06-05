import { Analyst, BacktestRun, CorrelationData, DailyPnL, EquityPoint, GroupMessage, MCResult, OpenPosition, PaperPosition, PaperStats, PaperTrade, PriceTick, RiskStatus, ShadowPair, ShadowSummary, WalkForwardRun, WFWindow } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// Suppress unused-import warnings — types are used as generics above
type _Suppress = ShadowPair | ShadowSummary;

export const api = {
  accounts: () => get<Analyst[]>("/api/accounts/"),
  combinedEquity: () => get<EquityPoint[]>("/api/accounts/combined-equity"),
  analystEquity: (id: number) => get<EquityPoint[]>(`/api/accounts/${id}/equity-curve`),
  analystTrades: (id: number) => get<unknown[]>(`/api/accounts/${id}/trades`),
  prices: () => get<Record<string, PriceTick>>("/api/prices/"),
  messages: () => get<GroupMessage[]>("/api/messages/"),
  openTrade: (payload: unknown) => post<unknown>("/api/trades/open", payload),
  closeTrade: (id: number, exit_price: number) =>
    post<unknown>(`/api/trades/${id}/close`, { exit_price }),
  postMessage: (payload: unknown) => post<unknown>("/api/messages/", payload),
  riskStatus: () => get<RiskStatus>("/api/risk/status"),
  resetAnalyst: (id: number) => post<{ ok: boolean; analyst: string }>(`/api/risk/reset/${id}`, {}),
  backtestRun: (days?: number) =>
    post<{ message: string; count: number }>(`/api/backtest/run${days ? `?days=${days}` : ""}`, {}),
  backtestLatest: () => get<BacktestRun[]>("/api/backtest/latest"),
  backtestAllRuns: () => get<BacktestRun[]>("/api/backtest/runs"),
  backtestEquity: (id: number) => get<[string, number][]>(`/api/backtest/runs/${id}/equity`),
  backtestStatus: () => get<Record<string, number>>("/api/backtest/status"),
  backtestCancel: () => post<{ cancelled: number }>("/api/backtest/cancel", {}),
  paperStats: () => get<PaperStats>("/api/paper/stats"),
  paperPositions: () => get<PaperPosition[]>("/api/paper/positions"),
  paperTrades: () => get<PaperTrade[]>("/api/paper/trades"),
  paperReset: () => post<{ ok: boolean; reset: number }>("/api/paper/reset", {}),
  shadowCompare: () => get<ShadowPair[]>("/api/shadow/compare"),
  shadowSummary: () => get<ShadowSummary>("/api/shadow/summary"),
  walkForwardRun: (trainDays?: number, testDays?: number, stepDays?: number) => {
    const p = new URLSearchParams();
    if (trainDays) p.set("train_days", String(trainDays));
    if (testDays)  p.set("test_days",  String(testDays));
    if (stepDays)  p.set("step_days",  String(stepDays));
    return post<{ message: string; count: number }>(`/api/backtest/walk-forward?${p}`, {});
  },
  walkForwardLatest: () => get<WalkForwardRun[]>("/api/backtest/walk-forward/latest"),
  walkForwardStatus: () => get<Record<string, number>>("/api/backtest/walk-forward/status"),
  walkForwardWindows: (id: number) => get<WFWindow[]>(`/api/backtest/walk-forward/${id}/windows`),
  openPositions: () => get<OpenPosition[]>("/api/accounts/positions/open"),
  dailyPnL: () => get<DailyPnL[]>("/api/accounts/daily-pnl"),
  correlation: () => get<CorrelationData>("/api/accounts/correlation"),
  togglePause: (id: number) => post<{ ok: boolean; action: string; analyst: string }>(`/api/risk/toggle/${id}`, {}),
  monteCarloLatest: (nSims = 1000) => get<MCResult[]>(`/api/backtest/monte-carlo/latest?n_sims=${nSims}`),
  monteCarloSingle: (runId: number, nSims = 1000) => get<MCResult>(`/api/backtest/monte-carlo/${runId}?n_sims=${nSims}`),
};
