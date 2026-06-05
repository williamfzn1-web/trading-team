"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ShadowPair, ShadowSummary } from "@/lib/types";
import { toLocalDate } from "@/lib/time";

export default function ShadowPanel() {
  const [summary, setSummary] = useState<ShadowSummary | null>(null);
  const [pairs, setPairs] = useState<ShadowPair[]>([]);

  const load = useCallback(() => {
    api.shadowSummary().then(setSummary).catch(() => {});
    api.shadowCompare().then(setPairs).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, [load]);

  const noData = !summary || summary.pairs === 0;

  return (
    <div className="mb-5 bg-[#131924] rounded-xl border border-[#1e2636] overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-[#1e2636]">
        <div className="w-2 h-2 rounded-full bg-purple-400" />
        <span className="text-sm font-semibold text-white">影子分析師對比</span>
        <span className="text-[10px] text-gray-500 bg-[#1e2636] px-2 py-0.5 rounded-full">
          Live vs Shadow · 滑點分析
        </span>
      </div>

      {/* Summary stats */}
      {!noData && summary && (
        <div className="grid grid-cols-4 divide-x divide-[#1e2636] border-b border-[#1e2636]">
          {[
            {
              label: "配對筆數",
              value: `${summary.pairs}`,
              color: "text-white",
            },
            {
              label: "平均進場滑點",
              value: summary.avg_entry_slippage !== undefined
                ? `${summary.avg_entry_slippage >= 0 ? "+" : ""}$${summary.avg_entry_slippage.toFixed(2)}`
                : "-",
              color: (summary.avg_entry_slippage ?? 0) <= 0 ? "text-green-400" : "text-red-400",
            },
            {
              label: "平均出場滑點",
              value: summary.avg_exit_slippage !== undefined
                ? `${summary.avg_exit_slippage >= 0 ? "+" : ""}$${summary.avg_exit_slippage.toFixed(2)}`
                : "-",
              color: (summary.avg_exit_slippage ?? 0) <= 0 ? "text-green-400" : "text-red-400",
            },
            {
              label: "累計損益差",
              value: summary.total_pnl_diff !== undefined
                ? `${summary.total_pnl_diff >= 0 ? "+" : ""}$${summary.total_pnl_diff.toFixed(2)}`
                : "-",
              sub: "真實 − 影子",
              color: (summary.total_pnl_diff ?? 0) >= 0 ? "text-green-400" : "text-red-400",
            },
          ].map((s) => (
            <div key={s.label} className="px-5 py-3">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">{s.label}</p>
              <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
              {"sub" in s && <p className="text-[11px] text-gray-600">{s.sub}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Trade table or waiting message */}
      {noData ? (
        <div className="px-5 py-8 text-center">
          <p className="text-gray-500 text-sm">等待真實倉啟動後自動開始配對</p>
          <p className="text-gray-600 text-xs mt-1">
            當 TRADING_MODE=live 時，每一筆真實交易都會自動建立影子副本
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto max-h-64 overflow-y-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-gray-500 uppercase text-[10px] border-b border-[#1e2636] sticky top-0 bg-[#131924]">
                {["分析師", "標的", "方向", "進場滑點", "出場滑點", "真實PnL", "影子PnL", "損益差", "時間"].map(
                  (h) => (
                    <th key={h} className="px-4 py-2 text-left font-medium whitespace-nowrap">
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {pairs.map((p, i) => (
                <tr key={i} className="border-b border-[#1a2030] hover:bg-[#1a2030] transition-colors">
                  <td className="px-4 py-2 text-gray-300 whitespace-nowrap">{p.analyst}</td>
                  <td className="px-4 py-2 text-white font-medium">{p.symbol}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      p.side === "long" ? "bg-green-900/60 text-green-300" : "bg-red-900/60 text-red-300"
                    }`}>
                      {p.side === "long" ? "多" : "空"}
                    </span>
                  </td>
                  <td className={`px-4 py-2 font-mono text-[11px] ${
                    (p.diff?.entry_slippage ?? 0) <= 0 ? "text-green-400" : "text-red-400"
                  }`}>
                    {p.diff ? `${p.diff.entry_slippage >= 0 ? "+" : ""}$${p.diff.entry_slippage.toFixed(2)}` : "-"}
                  </td>
                  <td className={`px-4 py-2 font-mono text-[11px] ${
                    (p.diff?.exit_slippage ?? 0) <= 0 ? "text-green-400" : "text-red-400"
                  }`}>
                    {p.diff ? `${p.diff.exit_slippage >= 0 ? "+" : ""}$${p.diff.exit_slippage.toFixed(2)}` : "-"}
                  </td>
                  <td className={`px-4 py-2 font-semibold ${
                    p.live.realized_pnl >= 0 ? "text-green-400" : "text-red-400"
                  }`}>
                    {p.live.realized_pnl >= 0 ? "+" : ""}${p.live.realized_pnl.toFixed(2)}
                  </td>
                  <td className={`px-4 py-2 font-semibold ${
                    (p.shadow?.realized_pnl ?? 0) >= 0 ? "text-cyan-400" : "text-orange-400"
                  }`}>
                    {p.shadow ? `${p.shadow.realized_pnl >= 0 ? "+" : ""}$${p.shadow.realized_pnl.toFixed(2)}` : "-"}
                  </td>
                  <td className={`px-4 py-2 font-mono text-[11px] ${
                    (p.diff?.pnl_diff ?? 0) >= 0 ? "text-green-400" : "text-red-400"
                  }`}>
                    {p.diff ? `${p.diff.pnl_diff >= 0 ? "+" : ""}$${p.diff.pnl_diff.toFixed(2)}` : "-"}
                  </td>
                  <td className="px-4 py-2 text-gray-500 whitespace-nowrap text-[11px]">
                    {toLocalDate(p.exit_time)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
