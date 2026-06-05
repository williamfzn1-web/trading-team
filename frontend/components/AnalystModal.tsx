"use client";

import { useEffect, useState } from "react";
import { Analyst, EquityPoint } from "@/lib/types";
import { api } from "@/lib/api";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Trade {
  id: number;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  leverage: number;
  realized_pnl: number;
  status: string;
  entry_time: string;
  exit_time: string | null;
}

interface Props {
  analyst: Analyst;
  onClose: () => void;
}

export default function AnalystModal({ analyst, onClose }: Props) {
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    api.analystEquity(analyst.id).then(setEquity).catch(() => {});
    api.analystTrades(analyst.id).then((data) => setTrades(data as Trade[])).catch(() => {});
  }, [analyst.id]);

  const profit = analyst.total_pnl >= 0;
  const sign = profit ? "+" : "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#161b27] rounded-2xl border border-[#1e2636] w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-[#1e2636]">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold shrink-0"
            style={{ backgroundColor: analyst.avatar_color }}
          >
            {analyst.name.split(" ").map((n) => n[0]).join("")}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white font-bold">{analyst.name}</p>
            <p className="text-gray-500 text-sm truncate">{analyst.strategy_description}</p>
          </div>
          <button
            onClick={onClose}
            className="ml-auto text-gray-500 hover:text-white text-xl leading-none shrink-0"
          >
            ✕
          </button>
        </div>

        {/* Stats row 1: 帳戶總額 / 帳戶餘額 / 總盈虧% / 勝率 */}
        <div className="grid grid-cols-4 gap-3 px-6 py-4 border-b border-[#1e2636]">
          {[
            {
              label: "帳戶總額",
              value: `$${analyst.total_equity.toLocaleString("en-US", { maximumFractionDigits: 0 })}`,
            },
            {
              label: "帳戶餘額",
              value: `$${analyst.current_balance.toLocaleString("en-US", { maximumFractionDigits: 0 })}`,
              color: "text-gray-300",
            },
            {
              label: "總盈虧",
              value: `${sign}${analyst.pnl_pct.toFixed(2)}%`,
              color: profit ? "text-green-400" : "text-red-400",
            },
            { label: "勝率", value: `${analyst.win_rate.toFixed(1)}%` },
          ].map(({ label, value, color }) => (
            <div key={label}>
              <p className="text-gray-600 text-[10px] uppercase tracking-wider">{label}</p>
              <p className={`text-white font-bold text-lg ${color ?? ""}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Stats row 2: 已實現 / 浮動 / 佔用保證金 / 最大回撤 / Sharpe */}
        <div className="grid grid-cols-5 gap-3 px-6 py-3 border-b border-[#1e2636]">
          {[
            { label: "已實現", value: `${analyst.realized_pnl >= 0 ? "+" : ""}$${analyst.realized_pnl.toFixed(0)}`, color: analyst.realized_pnl >= 0 ? "text-green-400" : "text-red-400" },
            { label: "浮動盈虧", value: `${analyst.unrealized_pnl >= 0 ? "+" : ""}$${analyst.unrealized_pnl.toFixed(0)}`, color: analyst.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400" },
            { label: "佔用保證金", value: `$${analyst.occupied_margin.toLocaleString("en-US", { maximumFractionDigits: 0 })}`, color: analyst.occupied_margin > 0 ? "text-yellow-400" : "text-gray-500" },
            { label: "最大回撤", value: `${analyst.max_drawdown.toFixed(1)}%`, color: analyst.max_drawdown > 20 ? "text-red-400" : "text-yellow-400" },
            { label: "Sharpe", value: analyst.sharpe_ratio.toFixed(2), color: analyst.sharpe_ratio >= 1 ? "text-green-400" : "text-gray-300" },
          ].map(({ label, value, color }) => (
            <div key={label}>
              <p className="text-gray-600 text-[10px] uppercase tracking-wider">{label}</p>
              <p className={`font-semibold text-base ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Equity curve */}
        {equity.length > 1 && (
          <div className="px-6 pt-4">
            <p className="text-gray-500 text-[11px] uppercase tracking-widest mb-2">資金曲線</p>
            <ResponsiveContainer width="100%" height={140}>
              <AreaChart data={equity}>
                <defs>
                  <linearGradient id="analystGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={analyst.avatar_color} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={analyst.avatar_color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="timestamp" hide />
                <YAxis domain={["auto", "auto"]} hide />
                <Tooltip
                  contentStyle={{
                    background: "#0f1117",
                    border: "1px solid #1e2636",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v: number) => [
                    `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`,
                    "餘額",
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="balance"
                  stroke={analyst.avatar_color}
                  strokeWidth={2}
                  fill="url(#analystGrad)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Recent trades */}
        <div className="px-6 py-4">
          <p className="text-gray-500 text-[11px] uppercase tracking-widest mb-3">
            近期交易（{trades.length}）
          </p>
          <div className="space-y-1.5 max-h-52 overflow-y-auto scrollbar-hide">
            {trades.slice(0, 20).map((t) => (
              <div
                key={t.id}
                className="flex items-center gap-3 px-3 py-2 rounded-lg bg-[#0f1117] text-xs"
              >
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 ${
                    t.side === "long"
                      ? "bg-green-950 text-green-400"
                      : "bg-red-950 text-red-400"
                  }`}
                >
                  {t.side.toUpperCase()}
                </span>
                <span className="text-gray-300 font-medium w-20 shrink-0">{t.symbol}</span>
                <span className="text-gray-500">
                  ${t.entry_price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                </span>
                <span className="text-gray-600">→</span>
                <span className="text-gray-400">
                  {t.exit_price
                    ? `$${t.exit_price.toLocaleString("en-US", { maximumFractionDigits: 2 })}`
                    : "開倉中"}
                </span>
                <span className="ml-auto font-semibold shrink-0">
                  {t.status === "open" ? (
                    <span className="text-blue-400">持倉中</span>
                  ) : (
                    <span className={t.realized_pnl >= 0 ? "text-green-400" : "text-red-400"}>
                      {t.realized_pnl >= 0 ? "+" : ""}${t.realized_pnl.toFixed(0)}
                    </span>
                  )}
                </span>
              </div>
            ))}
            {trades.length === 0 && (
              <p className="text-gray-600 text-sm text-center py-4">尚無交易記錄</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
