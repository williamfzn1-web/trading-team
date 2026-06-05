"use client";

import { Analyst, EquityPoint } from "@/lib/types";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  analysts: Analyst[];
  equity: EquityPoint[];
}

function Stat({
  label,
  value,
  sub,
  subClass,
}: {
  label: string;
  value: string;
  sub?: string;
  subClass?: string;
}) {
  return (
    <div className="bg-[#161b27] rounded-xl p-4 border border-[#1e2636]">
      <p className="text-gray-500 text-[11px] uppercase tracking-widest mb-1">{label}</p>
      <p className="text-white text-2xl font-bold leading-tight">{value}</p>
      {sub && <p className={`text-sm mt-1 ${subClass ?? "text-gray-400"}`}>{sub}</p>}
    </div>
  );
}

export default function OverviewPanel({ analysts, equity }: Props) {
  const totalCapital = analysts.reduce((s, a) => s + a.initial_capital, 0);
  const totalEquity = analysts.reduce((s, a) => s + a.total_equity, 0);
  const totalRealized = analysts.reduce((s, a) => s + a.realized_pnl, 0);
  const totalUnrealized = analysts.reduce((s, a) => s + a.unrealized_pnl, 0);
  const totalOccupiedMargin = analysts.reduce((s, a) => s + a.occupied_margin, 0);
  const totalPnl = totalRealized + totalUnrealized;
  const totalPct = totalCapital > 0 ? (totalPnl / totalCapital) * 100 : 0;
  const openPositions = analysts.reduce((s, a) => s + a.open_positions, 0);
  const activeAnalysts = analysts.filter((a) => a.open_positions > 0).length;
  const marginUtilPct = totalCapital > 0 ? (totalOccupiedMargin / totalCapital) * 100 : 0;

  const pnlClass = totalPnl >= 0 ? "text-green-400" : "text-red-400";
  const pnlSign = totalPnl >= 0 ? "+" : "";

  return (
    <div className="p-5 space-y-4">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <Stat
          label="總帳戶總額"
          value={`$${totalEquity.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={`本金 $${totalCapital.toLocaleString()}`}
        />
        <Stat
          label="總盈虧（已實現）"
          value={`${pnlSign}$${Math.abs(totalRealized).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={`${pnlSign}${totalPct.toFixed(2)}%`}
          subClass={pnlClass}
        />
        <Stat
          label="佔用保證金"
          value={`$${totalOccupiedMargin.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={`佔用率 ${marginUtilPct.toFixed(1)}%`}
          subClass={marginUtilPct > 40 ? "text-red-400" : marginUtilPct > 20 ? "text-yellow-400" : "text-green-400"}
        />
        <Stat
          label="持倉活躍"
          value={`${activeAnalysts} / ${analysts.length}`}
          sub={`共 ${openPositions} 個持倉`}
          subClass="text-blue-400"
        />
      </div>

      {equity.length > 1 && (
        <div className="bg-[#161b27] rounded-xl p-4 border border-[#1e2636]">
          <p className="text-gray-500 text-[11px] uppercase tracking-widest mb-3">
            資金曲線（10 帳戶合計）
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={equity}>
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
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
                labelStyle={{ color: "#6b7280" }}
                formatter={(v: number) => [
                  `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`,
                  "合計淨值",
                ]}
              />
              <Area
                type="monotone"
                dataKey="balance"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#grad)"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
