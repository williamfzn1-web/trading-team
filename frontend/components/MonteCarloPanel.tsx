"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { MCResult } from "@/lib/types";

function ProbBadge({ pct }: { pct: number }) {
  const color =
    pct >= 70
      ? "text-green-300 bg-green-900/50"
      : pct >= 50
        ? "text-yellow-300 bg-yellow-900/50"
        : "text-red-400 bg-red-900/50";
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${color}`}>
      {pct.toFixed(1)}%
    </span>
  );
}

function ReturnRange({
  p50,
  p5,
  p95,
}: {
  p50: number;
  p5: number;
  p95: number;
}) {
  const sign = (n: number) => (n >= 0 ? "+" : "");
  const color = p50 >= 0 ? "text-green-400" : "text-red-400";
  return (
    <div className="leading-none">
      <span className={`font-bold ${color}`}>
        {sign(p50)}
        {p50.toFixed(1)}%
      </span>
      <span className="text-gray-600 text-[10px] ml-1">
        [{sign(p5)}
        {p5.toFixed(0)}% ~ {sign(p95)}
        {p95.toFixed(0)}%]
      </span>
    </div>
  );
}

export default function MonteCarloPanel() {
  const [results, setResults] = useState<MCResult[]>([]);
  const [selected, setSelected] = useState<MCResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [nSims, setNSims] = useState(1000);
  const [open, setOpen] = useState(true);

  const load = useCallback(
    (sims = nSims) => {
      setLoading(true);
      api
        .monteCarloLatest(sims)
        .then((data) => {
          setResults(data);
          // Restore selected with fresh data
          setSelected((prev) =>
            prev ? (data.find((r) => r.strategy === prev.strategy) ?? null) : null
          );
        })
        .catch(() => {})
        .finally(() => setLoading(false));
    },
    [nSims]
  );

  useEffect(() => {
    load();
  }, [load]);

  const handleRun = (sims: number) => {
    setNSims(sims);
    load(sims);
  };

  const chartData = selected
    ? selected.bands.x_labels.map((x, i) => ({
        trade: x,
        p5: selected.bands.p5[i],
        p25: selected.bands.p25[i],
        p50: selected.bands.p50[i],
        p75: selected.bands.p75[i],
        p95: selected.bands.p95[i],
      }))
    : [];

  const isRunning = loading;

  return (
    <div className="mb-5 bg-[#131924] rounded-xl border border-[#1e2636] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e2636]">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <div
            className={`w-2 h-2 rounded-full ${isRunning ? "bg-purple-400 animate-pulse" : "bg-purple-500"}`}
          />
          <span className="text-sm font-semibold text-white">Monte Carlo</span>
          <span className="text-[10px] text-gray-500 bg-[#1e2636] px-2 py-0.5 rounded-full">
            Bootstrap Resampling · {nSims.toLocaleString()} 次模擬
          </span>
          <span className="text-gray-600 text-xs ml-1">{open ? "▲" : "▼"}</span>
        </button>
        <div className="flex items-center gap-2">
          {[1000, 5000, 10000].map((n) => (
            <button
              key={n}
              onClick={() => handleRun(n)}
              disabled={isRunning}
              className={`text-[11px] px-2 py-1 rounded border transition-colors disabled:opacity-40 ${
                nSims === n
                  ? "text-purple-300 border-purple-700 bg-purple-900/30"
                  : "text-gray-500 border-[#1e2636] hover:text-gray-300"
              }`}
            >
              {n.toLocaleString()}
            </button>
          ))}
        </div>
      </div>

      {open && (
        results.length === 0 ? (
          <p className="text-gray-600 text-sm text-center py-8">
            {isRunning
              ? "計算中..."
              : "尚無數據 — 請先執行回測再查看 Monte Carlo"}
          </p>
        ) : (
          <>
            {/* Summary table */}
            <div className="overflow-x-auto border-b border-[#1e2636]">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-gray-500 uppercase text-[10px] border-b border-[#1e2636]">
                    {[
                      "策略",
                      "交易數",
                      "獲利概率",
                      "中位回報 [p5 ~ p95]",
                      "中位最大回撤",
                      "最壞情境回撤",
                      "崩潰概率 (<-50%)",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2 text-left font-medium whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr
                      key={r.run_id}
                      onClick={() =>
                        setSelected(
                          selected?.run_id === r.run_id ? null : r
                        )
                      }
                      className={`border-b border-[#1a2030] hover:bg-[#1a2030] transition-colors cursor-pointer ${
                        selected?.run_id === r.run_id
                          ? "bg-[#1a2030] ring-1 ring-inset ring-purple-800"
                          : ""
                      }`}
                    >
                      <td className="px-4 py-2.5 text-white font-medium">
                        {r.strategy}
                      </td>
                      <td className="px-4 py-2.5 text-gray-400">{r.n_trades}</td>
                      <td className="px-4 py-2.5">
                        <ProbBadge pct={r.prob_profit_pct} />
                      </td>
                      <td className="px-4 py-2.5">
                        <ReturnRange
                          p50={r.return.p50}
                          p5={r.return.p5}
                          p95={r.return.p95}
                        />
                      </td>
                      <td className="px-4 py-2.5 text-orange-400">
                        {r.max_drawdown.p50.toFixed(1)}%
                      </td>
                      <td className="px-4 py-2.5 text-red-400">
                        {r.max_drawdown.worst.toFixed(1)}%
                      </td>
                      <td className="px-4 py-2.5 text-gray-500">
                        {r.prob_ruin_pct.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Fan chart */}
            {selected && chartData.length > 0 && (
              <div className="p-5">
                <div className="text-[11px] text-gray-400 mb-3">
                  <span className="text-white font-medium">{selected.strategy}</span>
                  {" "}— {selected.n_sims.toLocaleString()} 次 Bootstrap 模擬路徑分位數
                </div>

                <ResponsiveContainer width="100%" height={240}>
                  <LineChart
                    data={chartData}
                    margin={{ top: 5, right: 20, left: 10, bottom: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e2636" />
                    <XAxis
                      dataKey="trade"
                      tick={{ fill: "#6b7280", fontSize: 10 }}
                      label={{
                        value: "累積交易次數",
                        position: "insideBottom",
                        fill: "#6b7280",
                        fontSize: 10,
                        dy: 12,
                      }}
                    />
                    <YAxis
                      tick={{ fill: "#6b7280", fontSize: 10 }}
                      tickFormatter={(v) =>
                        `$${(v / 1000).toFixed(1)}k`
                      }
                      width={52}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#131924",
                        border: "1px solid #1e2636",
                        borderRadius: 8,
                        fontSize: 11,
                      }}
                      formatter={(v: number, name: string) => [
                        `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                        name,
                      ]}
                      labelFormatter={(l) => `第 ${l} 筆交易後`}
                    />
                    <Legend wrapperStyle={{ fontSize: 10, color: "#9ca3af", paddingTop: 8 }} />
                    <Line
                      type="monotone"
                      dataKey="p95"
                      stroke="#10b981"
                      dot={false}
                      strokeWidth={1}
                      strokeDasharray="5 3"
                      name="P95 (最佳 5%)"
                    />
                    <Line
                      type="monotone"
                      dataKey="p75"
                      stroke="#22c55e"
                      dot={false}
                      strokeWidth={1.5}
                      name="P75"
                    />
                    <Line
                      type="monotone"
                      dataKey="p50"
                      stroke="#ffffff"
                      dot={false}
                      strokeWidth={2.5}
                      name="P50 中位數"
                    />
                    <Line
                      type="monotone"
                      dataKey="p25"
                      stroke="#f97316"
                      dot={false}
                      strokeWidth={1.5}
                      name="P25"
                    />
                    <Line
                      type="monotone"
                      dataKey="p5"
                      stroke="#ef4444"
                      dot={false}
                      strokeWidth={1}
                      strokeDasharray="5 3"
                      name="P5 (最差 5%)"
                    />
                  </LineChart>
                </ResponsiveContainer>

                {/* Key stats */}
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    {
                      label: "獲利概率",
                      value: `${selected.prob_profit_pct.toFixed(1)}%`,
                      color:
                        selected.prob_profit_pct >= 70
                          ? "text-green-400"
                          : selected.prob_profit_pct >= 50
                            ? "text-yellow-400"
                            : "text-red-400",
                    },
                    {
                      label: "中位回報",
                      value: `${selected.return.p50 >= 0 ? "+" : ""}${selected.return.p50.toFixed(1)}%`,
                      color:
                        selected.return.p50 >= 0
                          ? "text-green-400"
                          : "text-red-400",
                    },
                    {
                      label: "P95 最大回撤",
                      value: `-${selected.max_drawdown.p95.toFixed(1)}%`,
                      color: "text-orange-400",
                    },
                    {
                      label: "最壞情境回撤",
                      value: `-${selected.max_drawdown.worst.toFixed(1)}%`,
                      color: "text-red-400",
                    },
                  ].map(({ label, value, color }) => (
                    <div
                      key={label}
                      className="bg-[#0f1117] rounded-lg p-3 text-center border border-[#1e2636]"
                    >
                      <div className="text-[10px] text-gray-500 mb-1">{label}</div>
                      <div className={`text-xl font-bold ${color}`}>{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )
      )}
    </div>
  );
}
