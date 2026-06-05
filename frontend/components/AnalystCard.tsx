"use client";

import { Analyst } from "@/lib/types";

interface Props {
  analyst: Analyst;
  onClick: () => void;
  isPaused?: boolean;
  sizeMultiplier?: number;
  onTogglePause?: (e: React.MouseEvent) => void;
}

function Metric({
  label,
  value,
  good,
  invert,
}: {
  label: string;
  value: string;
  good?: boolean;
  invert?: boolean;
}) {
  const resolved = invert ? !good : good;
  const color =
    good === undefined
      ? "text-gray-300"
      : resolved
        ? "text-green-400"
        : "text-yellow-400";
  return (
    <div className="bg-[#0f1117] rounded-lg px-2 py-1.5">
      <p className="text-gray-600 text-[10px] uppercase tracking-wider">{label}</p>
      <p className={`text-sm font-semibold ${color}`}>{value}</p>
    </div>
  );
}

export default function AnalystCard({ analyst, onClick, isPaused, sizeMultiplier, onTogglePause }: Props) {
  const profit = analyst.total_pnl >= 0;
  const sign = profit ? "+" : "";
  const initials = analyst.name
    .split(" ")
    .map((n) => n[0])
    .join("");
  const marginUtilPct =
    analyst.current_balance + analyst.occupied_margin > 0
      ? (analyst.occupied_margin / (analyst.current_balance + analyst.occupied_margin)) * 100
      : 0;

  return (
    <div
      onClick={onClick}
      className={`bg-[#161b27] rounded-xl p-4 border cursor-pointer transition-all hover:shadow-xl hover:-translate-y-0.5 ${
        isPaused
          ? "border-red-900 hover:border-red-700 opacity-75"
          : "border-[#1e2636] hover:border-[#2d3a52]"
      }`}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
          style={{ backgroundColor: analyst.avatar_color }}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-semibold truncate">{analyst.name}</p>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded font-medium"
            style={{
              backgroundColor: analyst.avatar_color + "25",
              color: analyst.avatar_color,
            }}
          >
            {analyst.strategy}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {isPaused && (
            <span className="text-[10px] px-2 py-1 rounded-full font-medium bg-red-950 text-red-400">
              暫停
            </span>
          )}
          {!isPaused && sizeMultiplier !== undefined && sizeMultiplier < 1 && (
            <span className="text-[10px] px-1.5 py-1 rounded-full font-medium bg-orange-950 text-orange-400">
              ×{sizeMultiplier}
            </span>
          )}
          {!isPaused && (
            <span
              className={`text-[10px] px-2 py-1 rounded-full font-medium ${
                analyst.open_positions > 0
                  ? "bg-green-950 text-green-400"
                  : "bg-[#0f1117] text-gray-600"
              }`}
            >
              {analyst.open_positions > 0 ? `${analyst.open_positions}倉` : "觀望"}
            </span>
          )}
          {onTogglePause && (
            <button
              onClick={onTogglePause}
              title={isPaused ? "恢復交易" : "暫停交易"}
              className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] transition-colors ${
                isPaused
                  ? "bg-green-900 hover:bg-green-700 text-green-400"
                  : "bg-[#0f1117] hover:bg-red-950 text-gray-500 hover:text-red-400"
              }`}
            >
              {isPaused ? "▶" : "⏸"}
            </button>
          )}
        </div>
      </div>

      {/* Balance */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-gray-600 text-[10px] uppercase tracking-wider">帳戶總額</p>
          <p className="text-white text-xl font-bold">
            ${analyst.total_equity.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </p>
          <p className={`text-sm font-medium ${profit ? "profit" : "loss"}`}>
            {sign}${Math.abs(analyst.total_pnl).toLocaleString("en-US", { maximumFractionDigits: 0 })}{" "}
            <span className="text-xs opacity-75">
              ({sign}{analyst.pnl_pct.toFixed(2)}%)
            </span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-gray-600 text-[10px] uppercase tracking-wider">帳戶餘額</p>
          <p className="text-gray-300 text-sm font-semibold">
            ${analyst.current_balance.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </p>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-1.5 mb-3">
        <Metric label="勝率" value={`${analyst.win_rate.toFixed(1)}%`} good={analyst.win_rate >= 55} />
        <Metric label="Sharpe" value={analyst.sharpe_ratio.toFixed(2)} good={analyst.sharpe_ratio >= 1.0} />
        <Metric label="最大回撤" value={`${analyst.max_drawdown.toFixed(1)}%`} good={analyst.max_drawdown <= 20} invert />
        <Metric label="交易數" value={analyst.total_trades.toString()} />
      </div>

      {/* Margin utilization bar */}
      {analyst.open_positions > 0 && (
        <div className="mb-2.5">
          <div className="flex justify-between text-[10px] text-gray-600 mb-1">
            <span>保證金使用率</span>
            <span>{marginUtilPct.toFixed(1)}%</span>
          </div>
          <div className="h-1 bg-[#0f1117] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                marginUtilPct > 50 ? "bg-red-500" : marginUtilPct > 30 ? "bg-yellow-500" : "bg-green-500"
              }`}
              style={{ width: `${Math.min(marginUtilPct, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Footer: 已實現 / 佔用保證金 / 浮動 */}
      <div className="grid grid-cols-3 border-t border-[#1e2636] pt-2.5 text-[11px]">
        <div>
          <p className="text-gray-600">已實現</p>
          <p className={analyst.realized_pnl >= 0 ? "text-green-400" : "text-red-400"}>
            {analyst.realized_pnl >= 0 ? "+" : ""}${analyst.realized_pnl.toFixed(0)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-gray-600">佔用保證金</p>
          <p className={analyst.occupied_margin > 0 ? "text-yellow-400" : "text-gray-500"}>
            ${analyst.occupied_margin.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="text-right">
          <p className="text-gray-600">浮動</p>
          <p className={analyst.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}>
            {analyst.unrealized_pnl >= 0 ? "+" : ""}${analyst.unrealized_pnl.toFixed(0)}
          </p>
        </div>
      </div>
    </div>
  );
}
