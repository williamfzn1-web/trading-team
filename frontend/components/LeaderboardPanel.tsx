"use client";

import { useState } from "react";
import { Analyst } from "@/lib/types";

interface Props {
  analysts: Analyst[];
}

type MetricKey = "pnl_pct" | "sharpe_ratio" | "win_rate" | "max_drawdown";

const METRICS: {
  key: MetricKey;
  label: string;
  invert?: boolean;
  format: (v: number) => string;
  goodThreshold: number;
}[] = [
  { key: "pnl_pct", label: "總報酬", format: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`, goodThreshold: 0 },
  { key: "sharpe_ratio", label: "Sharpe", format: (v) => v.toFixed(2), goodThreshold: 0 },
  { key: "win_rate", label: "勝率", format: (v) => `${v.toFixed(1)}%`, goodThreshold: 50 },
  { key: "max_drawdown", label: "回撤", invert: true, format: (v) => `${v.toFixed(1)}%`, goodThreshold: 20 },
];

const RANK_COLORS = ["text-yellow-400", "text-gray-300", "text-orange-500"];

export default function LeaderboardPanel({ analysts }: Props) {
  const [metric, setMetric] = useState<MetricKey>("pnl_pct");

  const m = METRICS.find((x) => x.key === metric)!;
  const sorted = [...analysts].sort((a, b) =>
    m.invert ? a[metric] - b[metric] : b[metric] - a[metric]
  );
  const maxAbs = Math.max(...sorted.map((a) => Math.abs(a[metric])), 1);

  return (
    <div className="bg-[#161b27] rounded-xl border border-[#1e2636] overflow-hidden">
      {/* Header + metric selector */}
      <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-[#1e2636]">
        <span className="text-gray-500 text-[11px] uppercase tracking-wider mr-1">績效排行</span>
        {METRICS.map((mx) => (
          <button
            key={mx.key}
            onClick={() => setMetric(mx.key)}
            className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
              metric === mx.key
                ? "bg-indigo-600 text-white"
                : "bg-[#0f1117] text-gray-500 hover:text-gray-300"
            }`}
          >
            {mx.label}
          </button>
        ))}
      </div>

      {/* Ranked list */}
      <div className="divide-y divide-[#1e2636]">
        {sorted.map((a, i) => {
          const val = a[metric];
          const isGood = m.invert ? val <= m.goodThreshold : val >= m.goodThreshold;
          const barPct = (Math.abs(val) / maxAbs) * 100;

          return (
            <div
              key={a.id}
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#0f1117] transition-colors"
            >
              <span
                className={`text-[11px] font-bold w-4 text-center shrink-0 ${
                  RANK_COLORS[i] ?? "text-gray-600"
                }`}
              >
                {i + 1}
              </span>
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[9px] font-bold shrink-0"
                style={{ backgroundColor: a.avatar_color }}
              >
                {a.name.split(" ").map((n) => n[0]).join("")}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-gray-300 text-xs font-medium truncate">{a.name}</p>
                <div className="mt-1 h-1 bg-[#0f1117] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      isGood ? "bg-green-500" : "bg-red-500"
                    }`}
                    style={{ width: `${barPct}%` }}
                  />
                </div>
              </div>
              <span
                className={`text-sm font-semibold shrink-0 ${
                  isGood ? "text-green-400" : "text-red-400"
                }`}
              >
                {m.format(val)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
