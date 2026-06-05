"use client";

import { useEffect, useState } from "react";
import { RiskStatus, AnalystRiskStatus } from "@/lib/types";
import { api } from "@/lib/api";

function DrawdownBar({ pct, limit }: { pct: number; limit: number }) {
  const fill = Math.min((pct / limit) * 100, 100);
  const color =
    pct >= limit * 0.9 ? "bg-red-500" : pct >= limit * 0.6 ? "bg-yellow-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-[#0f1117] rounded-full h-1.5 overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${fill}%` }} />
      </div>
      <span className={`text-[11px] font-mono w-10 text-right ${pct >= limit ? "text-red-400" : "text-gray-400"}`}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

function AnalystRow({
  a,
  onReset,
}: {
  a: AnalystRiskStatus;
  onReset: (id: number) => void;
}) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-[#1a2030] last:border-0">
      {/* Status dot */}
      <div
        className={`w-2 h-2 rounded-full shrink-0 ${a.can_trade ? "bg-green-400" : "bg-red-400"}`}
      />

      {/* Name + strategy */}
      <div className="flex-1 min-w-0">
        <p className="text-white text-[12px] font-medium truncate">{a.name}</p>
        {!a.can_trade && a.pause_reason && (
          <p className="text-red-400 text-[10px] truncate">{a.pause_reason}</p>
        )}
      </div>

      {/* Streak badge */}
      {a.consecutive_losses > 0 && (
        <span
          className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
            a.consecutive_losses >= 5
              ? "bg-red-950 text-red-400"
              : a.consecutive_losses >= 3
                ? "bg-orange-950 text-orange-400"
                : "bg-yellow-950 text-yellow-400"
          }`}
        >
          {a.consecutive_losses}L
        </span>
      )}

      {/* Size multiplier */}
      {a.size_multiplier < 1 && (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-950 text-orange-400 font-medium shrink-0">
          ×{a.size_multiplier}
        </span>
      )}

      {/* Drawdown */}
      <span className="text-[11px] text-gray-500 font-mono w-12 text-right shrink-0">
        -{a.drawdown_pct.toFixed(1)}%
      </span>

      {/* Reset button */}
      {!a.can_trade && (
        <button
          onClick={() => onReset(a.id)}
          className="text-[10px] px-2 py-0.5 rounded border border-[#2d3a52] text-gray-400 hover:text-white hover:border-gray-500 transition-colors shrink-0"
        >
          解除
        </button>
      )}
    </div>
  );
}

export default function RiskPanel() {
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [open, setOpen] = useState(true);

  const load = () => api.riskStatus().then(setRisk).catch(() => {});

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  const handleReset = async (id: number) => {
    await api.resetAnalyst(id).catch(() => {});
    load();
  };

  if (!risk) return null;

  const { portfolio, analysts, rules } = risk;
  const cbActive = portfolio.circuit_breaker_active;

  return (
    <div className="bg-[#161b27] rounded-xl border border-[#1e2636] overflow-hidden mb-5">
      {/* Header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#1a2030] transition-colors"
      >
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${cbActive ? "bg-red-400 animate-pulse" : "bg-green-400"}`}
          />
          <span className="text-white text-sm font-semibold">風控儀表板</span>
          {cbActive && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-950 text-red-400 font-medium animate-pulse">
              熔斷器啟動
            </span>
          )}
        </div>
        <span className="text-gray-600 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          {/* Portfolio section */}
          <div className="bg-[#0f1117] rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-gray-500 text-[11px] uppercase tracking-wider">組合回撤</span>
              <span className="text-gray-500 text-[10px]">
                上限 {portfolio.drawdown_limit_pct.toFixed(0)}%
              </span>
            </div>
            <DrawdownBar pct={portfolio.drawdown_pct} limit={portfolio.drawdown_limit_pct} />
            <div className="flex justify-between text-[11px] text-gray-600 pt-0.5">
              <span>
                當前 ${portfolio.total_balance.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
              <span>
                峰值 ${portfolio.peak_balance.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
            </div>
            {cbActive && portfolio.circuit_breaker_msg && (
              <p className="text-red-400 text-[11px] pt-1">{portfolio.circuit_breaker_msg}</p>
            )}
          </div>

          {/* Analyst rows */}
          <div>
            <p className="text-gray-600 text-[10px] uppercase tracking-wider mb-2">分析師狀態</p>
            <div className="space-y-0">
              {analysts.map((a) => (
                <AnalystRow key={a.id} a={a} onReset={handleReset} />
              ))}
            </div>
          </div>

          {/* Rules summary */}
          <div className="flex flex-wrap gap-2 pt-1 border-t border-[#1e2636]">
            {[
              `每日虧損 -${rules.daily_loss_limit_pct.toFixed(0)}%`,
              `組合熔斷 -${rules.portfolio_drawdown_limit_pct.toFixed(0)}%`,
              `集中度 ≤${rules.max_same_direction}`,
              `${rules.consec_reduce_at}連虧→半倉`,
              `${rules.consec_pause_at}連虧→24h暫停`,
            ].map((label) => (
              <span
                key={label}
                className="text-[10px] px-2 py-0.5 rounded bg-[#0f1117] text-gray-500 border border-[#1e2636]"
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
