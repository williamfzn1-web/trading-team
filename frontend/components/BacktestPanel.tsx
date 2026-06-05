"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { BacktestRun } from "@/lib/types";

// ── Helpers ────────────────────────────────────────────────────────────────

function pct(v: number, decimals = 1) {
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(decimals)}%`;
}

function color(v: number) {
  return v >= 0 ? "text-green-400" : "text-red-400";
}

function StatusBadge({ status }: { status: BacktestRun["status"] }) {
  const map: Record<string, string> = {
    pending: "bg-gray-800 text-gray-400",
    running: "bg-blue-950 text-blue-400 animate-pulse",
    completed: "bg-green-950 text-green-400",
    failed: "bg-red-950 text-red-400",
  };
  const label: Record<string, string> = {
    pending: "等待中",
    running: "執行中",
    completed: "完成",
    failed: "失敗",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${map[status]}`}>
      {label[status]}
    </span>
  );
}

// ── Equity curve modal ─────────────────────────────────────────────────────

function EquityModal({ run, onClose }: { run: BacktestRun; onClose: () => void }) {
  const [curve, setCurve] = useState<{ t: string; balance: number }[]>([]);

  useEffect(() => {
    api.backtestEquity(run.id).then((raw) => {
      setCurve(raw.map(([t, balance]) => ({ t: t.slice(0, 10), balance })));
    });
  }, [run.id]);

  const profit = run.total_return_pct >= 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#161b27] rounded-2xl border border-[#2d3a52] w-full max-w-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-white font-bold text-lg">{run.strategy}</h2>
            <p className="text-gray-500 text-xs">
              {run.primary_symbol} · {run.period_days}天回測 · 1h
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">
            ×
          </button>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-3 mb-5">
          {[
            { label: "總報酬", value: pct(run.total_return_pct), good: profit },
            { label: "Sharpe", value: run.sharpe_ratio.toFixed(2), good: run.sharpe_ratio >= 1 },
            { label: "勝率", value: `${run.win_rate.toFixed(1)}%`, good: run.win_rate >= 50 },
            { label: "最大回撤", value: pct(-run.max_drawdown_pct), good: run.max_drawdown_pct <= 20 },
          ].map(({ label, value, good }) => (
            <div key={label} className="bg-[#0f1117] rounded-lg p-2.5">
              <p className="text-gray-600 text-[10px] uppercase tracking-wider">{label}</p>
              <p className={`text-sm font-bold ${good ? "text-green-400" : "text-red-400"}`}>
                {value}
              </p>
            </div>
          ))}
        </div>

        {/* Equity curve */}
        <div className="h-48">
          {curve.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curve}>
                <defs>
                  <linearGradient id="btGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={profit ? "#22c55e" : "#ef4444"} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={profit ? "#22c55e" : "#ef4444"} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2636" />
                <XAxis dataKey="t" tick={{ fontSize: 9, fill: "#4b5563" }} tickLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 9, fill: "#4b5563" }} tickLine={false} axisLine={false}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} width={45} />
                <Tooltip
                  contentStyle={{ background: "#161b27", border: "1px solid #2d3a52", borderRadius: 8, fontSize: 11 }}
                  formatter={(v: number) => [`$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`, "餘額"]}
                />
                <Area
                  type="monotone" dataKey="balance"
                  stroke={profit ? "#22c55e" : "#ef4444"}
                  fill="url(#btGrad)" strokeWidth={1.5} dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-600 text-sm">
              {run.status === "completed" ? "無交易數據" : "回測進行中..."}
            </div>
          )}
        </div>

        {/* Extra metrics */}
        <div className="flex flex-wrap gap-3 mt-4 text-[11px] text-gray-500 border-t border-[#1e2636] pt-3">
          <span>交易次數 <span className="text-gray-300">{run.total_trades}</span></span>
          <span>獲利因子 <span className="text-gray-300">{run.profit_factor.toFixed(2)}</span></span>
          <span>平均盈利 <span className="text-green-400">+${run.avg_win_usdt.toFixed(0)}</span></span>
          <span>平均虧損 <span className="text-red-400">-${run.avg_loss_usdt.toFixed(0)}</span></span>
          <span>期末資金 <span className="text-gray-300">${run.final_capital.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span></span>
        </div>
      </div>
    </div>
  );
}

// ── Main panel ─────────────────────────────────────────────────────────────

export default function BacktestPanel() {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selected, setSelected] = useState<BacktestRun | null>(null);
  const [running, setRunning] = useState(false);
  const [open, setOpen] = useState(true);
  const [days, setDays] = useState(180);
  const [progress, setProgress] = useState<{ done: number; total: number; active: string | null }>({
    done: 0,
    total: 0,
    active: null,
  });

  const loadLatest = useCallback(() => {
    api.backtestLatest().then(setRuns).catch(() => {});
  }, []);

  const loadStatus = useCallback(() => {
    api.backtestStatus().then((s) => {
      const pending = s["pending"] ?? 0;
      const runningCount = s["running"] ?? 0;
      const completed = s["completed"] ?? 0;
      const failed = s["failed"] ?? 0;
      const isRunning = runningCount + pending > 0;
      const total = pending + runningCount + completed + failed;

      setProgress({ done: completed + failed, total, active: s["active_strategy"] ?? null });
      setRunning(isRunning);
      loadLatest(); // always refresh results, not just when running
    }).catch(() => {});
  }, [loadLatest]);

  useEffect(() => {
    loadLatest();
    loadStatus();
  }, [loadLatest, loadStatus]);

  // Poll while running
  useEffect(() => {
    if (!running) return;
    const id = setInterval(loadStatus, 3000);
    return () => {
      clearInterval(id);
      // Final load when polling stops (all done)
      loadLatest();
    };
  }, [running, loadStatus, loadLatest]);

  const handleRun = async () => {
    setRunning(true);
    await api.backtestRun(days).catch(() => {});
    setTimeout(loadLatest, 1000);
  };

  const handleCancel = async () => {
    await api.backtestCancel().catch(() => {});
    setRunning(false);
    loadLatest();
  };

  const hasCompleted = runs.some((r) => r.status === "completed");

  return (
    <>
      <div className="bg-[#161b27] rounded-xl border border-[#1e2636] overflow-hidden mb-5">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setOpen((v) => !v)}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <span className="text-white text-sm font-semibold">歷史回測</span>
              <span className="text-gray-600 text-xs">{open ? "▲" : "▼"}</span>
            </button>
            {running && progress.total > 0 && (
              <span className="text-[11px] text-gray-500">
                {progress.done}/{progress.total} 完成
                {progress.active ? (
                  <span className="text-blue-400 ml-1">· {progress.active}</span>
                ) : null}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              disabled={running}
              className="bg-[#0f1117] border border-[#2d3a52] text-gray-400 text-[11px] rounded px-2 py-1 disabled:opacity-40"
            >
              <option value={180}>180天</option>
              <option value={365}>365天</option>
              <option value={540}>540天</option>
            </select>
            {running ? (
              <>
                <span className="text-[11px] px-3 py-1.5 rounded-lg font-medium bg-blue-950 text-blue-400 animate-pulse cursor-default">
                  回測中...
                </span>
                <button
                  onClick={handleCancel}
                  className="text-[11px] px-3 py-1.5 rounded-lg font-medium bg-red-950 text-red-400 hover:bg-red-900 hover:text-red-300 transition-colors"
                >
                  取消
                </button>
              </>
            ) : (
              <button
                onClick={handleRun}
                className="text-[11px] px-3 py-1.5 rounded-lg font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
              >
                執行回測
              </button>
            )}
          </div>
        </div>

        {open && (
          <div className="px-4 pb-4">
            {runs.length === 0 ? (
              <p className="text-gray-600 text-sm text-center py-6">
                {running ? "正在抓取歷史數據並模擬..." : "點擊「執行回測」開始"}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="text-gray-600 text-[10px] uppercase tracking-wider border-b border-[#1e2636]">
                      <th className="text-left py-2 pr-3 font-medium">策略</th>
                      <th className="text-left py-2 pr-3 font-medium">標的</th>
                      <th className="text-right py-2 pr-3 font-medium">報酬</th>
                      <th className="text-right py-2 pr-3 font-medium">Sharpe</th>
                      <th className="text-right py-2 pr-3 font-medium">勝率</th>
                      <th className="text-right py-2 pr-3 font-medium">最大回撤</th>
                      <th className="text-right py-2 pr-3 font-medium">獲利因子</th>
                      <th className="text-right py-2 font-medium">交易數</th>
                      <th className="text-center py-2 pl-3 font-medium">狀態</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr
                        key={r.id}
                        onClick={() => r.status === "completed" && setSelected(r)}
                        className={`border-b border-[#1a2030] last:border-0 ${
                          r.status === "completed"
                            ? "hover:bg-[#1a2030] cursor-pointer"
                            : "opacity-60"
                        }`}
                      >
                        <td className="py-2 pr-3 text-white font-medium">{r.strategy}</td>
                        <td className="py-2 pr-3 text-gray-500">{r.primary_symbol.replace("/USDT", "")}</td>
                        <td className={`py-2 pr-3 text-right font-mono font-semibold ${color(r.total_return_pct)}`}>
                          {r.status === "completed" ? pct(r.total_return_pct) : "—"}
                        </td>
                        <td className={`py-2 pr-3 text-right font-mono ${r.sharpe_ratio >= 1 ? "text-green-400" : r.sharpe_ratio >= 0 ? "text-yellow-400" : "text-red-400"}`}>
                          {r.status === "completed" ? r.sharpe_ratio.toFixed(2) : "—"}
                        </td>
                        <td className={`py-2 pr-3 text-right font-mono ${r.win_rate >= 55 ? "text-green-400" : r.win_rate >= 45 ? "text-yellow-400" : "text-red-400"}`}>
                          {r.status === "completed" ? `${r.win_rate.toFixed(1)}%` : "—"}
                        </td>
                        <td className={`py-2 pr-3 text-right font-mono ${r.max_drawdown_pct <= 15 ? "text-green-400" : r.max_drawdown_pct <= 25 ? "text-yellow-400" : "text-red-400"}`}>
                          {r.status === "completed" ? `-${r.max_drawdown_pct.toFixed(1)}%` : "—"}
                        </td>
                        <td className={`py-2 pr-3 text-right font-mono ${r.profit_factor >= 1.5 ? "text-green-400" : r.profit_factor >= 1 ? "text-yellow-400" : "text-red-400"}`}>
                          {r.status === "completed" ? r.profit_factor.toFixed(2) : "—"}
                        </td>
                        <td className="py-2 text-right text-gray-400">
                          {r.status === "completed" ? r.total_trades : "—"}
                        </td>
                        <td className="py-2 pl-3 text-center">
                          <StatusBadge status={r.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {hasCompleted && (
                  <p className="text-gray-700 text-[10px] mt-2 text-center">
                    點擊任一列查看資金曲線
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {selected && <EquityModal run={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
