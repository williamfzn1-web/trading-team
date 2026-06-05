"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PaperPosition, PaperStats, PaperTrade } from "@/lib/types";
import { toLocalDateTime } from "@/lib/time";

export default function PaperTradingPanel() {
  const [stats, setStats] = useState<PaperStats | null>(null);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [tab, setTab] = useState<"positions" | "trades">("positions");
  const [resetting, setResetting] = useState(false);

  const load = useCallback(() => {
    api.paperStats().then(setStats).catch(() => {});
    api.paperPositions().then(setPositions).catch(() => {});
    api.paperTrades().then(setTrades).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, [load]);

  const handleReset = async () => {
    if (!confirm("確認重置所有模擬倉？帳戶餘額將回到 $10,000，此操作無法復原。")) return;
    setResetting(true);
    try {
      await api.paperReset();
      load();
    } finally {
      setResetting(false);
    }
  };

  const fmtPnl = (n: number) =>
    `${n >= 0 ? "+" : ""}$${Math.abs(n).toFixed(2)}`;

  return (
    <div className="mb-5 bg-[#131924] rounded-xl border border-[#1e2636] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e2636]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-sm font-semibold text-white">模擬倉</span>
          <span className="text-[10px] text-gray-500 bg-[#1e2636] px-2 py-0.5 rounded-full">
            Phase 3C · Live Paper Trading
          </span>
        </div>
        <button
          onClick={handleReset}
          disabled={resetting}
          className="text-[11px] text-gray-500 hover:text-red-400 transition-colors px-3 py-1 rounded-md border border-[#1e2636] hover:border-red-800 disabled:opacity-40"
        >
          {resetting ? "重置中..." : "重置帳戶"}
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-5 divide-x divide-[#1e2636] border-b border-[#1e2636]">
          {[
            {
              label: "總資產",
              value: `$${stats.total_equity.toLocaleString("en", { maximumFractionDigits: 0 })}`,
              sub: `初始 $${stats.total_initial.toLocaleString()}`,
              color: "text-white",
            },
            {
              label: "總報酬",
              value: `${stats.total_return_pct >= 0 ? "+" : ""}${stats.total_return_pct.toFixed(1)}%`,
              sub: `已實現 ${fmtPnl(stats.realized_pnl)}`,
              color: stats.total_return_pct >= 0 ? "text-green-400" : "text-red-400",
            },
            {
              label: "未實現損益",
              value: fmtPnl(stats.unrealized_pnl ?? 0),
              sub: `${stats.open_positions} 個持倉`,
              color: (stats.unrealized_pnl ?? 0) >= 0 ? "text-cyan-400" : "text-orange-400",
            },
            {
              label: "勝率 / 交易數",
              value: `${stats.win_rate.toFixed(1)}%`,
              sub: `共 ${stats.total_trades} 筆`,
              color: "text-white",
            },
            {
              label: "獲利因子",
              value: stats.profit_factor >= 9 ? "N/A" : stats.profit_factor.toFixed(2),
              sub: "PF > 1.5 為目標",
              color:
                stats.profit_factor >= 1.5
                  ? "text-green-400"
                  : stats.profit_factor >= 1
                  ? "text-yellow-400"
                  : "text-red-400",
            },
          ].map((s) => (
            <div key={s.label} className="px-5 py-3">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">
                {s.label}
              </p>
              <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-[11px] text-gray-600">{s.sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-[#1e2636]">
        {(["positions", "trades"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2 text-xs font-medium transition-colors ${
              tab === t
                ? "text-white border-b-2 border-indigo-500"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t === "positions"
              ? `持倉中 (${positions.length})`
              : `成交紀錄 (${trades.length})`}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto max-h-64 overflow-y-auto">
        {tab === "positions" ? (
          positions.length === 0 ? (
            <p className="text-gray-600 text-sm text-center py-8">
              目前無持倉 — 策略引擎每 5 分鐘掃描一次訊號
            </p>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-gray-500 uppercase text-[10px] border-b border-[#1e2636] sticky top-0 bg-[#131924]">
                  {["分析師", "標的", "方向", "進場價", "現價", "未實現損益", "倉位", "SL", "TP", "進場時間"].map(
                    (h) => (
                      <th key={h} className="px-4 py-2 text-left font-medium whitespace-nowrap">
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-[#1a2030] hover:bg-[#1a2030] transition-colors"
                  >
                    <td className="px-4 py-2 text-gray-300 whitespace-nowrap">{p.analyst}</td>
                    <td className="px-4 py-2 text-white font-medium">{p.symbol}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          p.side === "long"
                            ? "bg-green-900/60 text-green-300"
                            : "bg-red-900/60 text-red-300"
                        }`}
                      >
                        {p.side === "long" ? "多" : "空"} {p.leverage}x
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-300">
                      ${p.entry_price.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-gray-400">
                      {p.current_price ? `$${p.current_price.toLocaleString()}` : "-"}
                    </td>
                    <td className={`px-4 py-2 font-semibold ${p.unrealized_pnl >= 0 ? "text-cyan-400" : "text-orange-400"}`}>
                      {fmtPnl(p.unrealized_pnl)}
                    </td>
                    <td className="px-4 py-2 text-gray-300">${p.quantity.toFixed(0)}</td>
                    <td className="px-4 py-2 text-red-400">
                      {p.stop_loss ? `$${p.stop_loss.toLocaleString()}` : "-"}
                    </td>
                    <td className="px-4 py-2 text-green-400">
                      {p.take_profit ? `$${p.take_profit.toLocaleString()}` : "-"}
                    </td>
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {toLocalDateTime(p.entry_time)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : trades.length === 0 ? (
          <p className="text-gray-600 text-sm text-center py-8">尚無成交紀錄</p>
        ) : (
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-gray-500 uppercase text-[10px] border-b border-[#1e2636] sticky top-0 bg-[#131924]">
                {["分析師", "標的", "方向", "進場價", "出場價", "盈虧", "出場時間"].map((h) => (
                  <th key={h} className="px-4 py-2 text-left font-medium whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-[#1a2030] hover:bg-[#1a2030] transition-colors"
                >
                  <td className="px-4 py-2 text-gray-300 whitespace-nowrap">{t.analyst}</td>
                  <td className="px-4 py-2 text-white font-medium">{t.symbol}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        t.side === "long"
                          ? "bg-green-900/60 text-green-300"
                          : "bg-red-900/60 text-red-300"
                      }`}
                    >
                      {t.side === "long" ? "多" : "空"} {t.leverage}x
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-300">
                    ${t.entry_price.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-gray-300">
                    {t.exit_price ? `$${t.exit_price.toLocaleString()}` : "-"}
                  </td>
                  <td
                    className={`px-4 py-2 font-semibold ${
                      t.realized_pnl >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {fmtPnl(t.realized_pnl)}
                  </td>
                  <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                    {toLocalDateTime(t.exit_time)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
