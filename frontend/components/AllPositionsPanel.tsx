"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { OpenPosition } from "@/lib/types";

type SortKey = "unrealized_pnl" | "margin" | "analyst_name" | "symbol";

function Th({
  label,
  sortBy,
  active,
  asc,
  onSort,
}: {
  label: string;
  sortBy?: SortKey;
  active?: boolean;
  asc?: boolean;
  onSort?: () => void;
}) {
  return (
    <th
      onClick={onSort}
      className={`px-3 py-2 text-left text-[10px] uppercase tracking-wider ${
        sortBy ? "cursor-pointer select-none" : ""
      } ${active ? "text-indigo-400" : "text-gray-500"}`}
    >
      {label}
      {sortBy && active ? (asc ? " ↑" : " ↓") : ""}
    </th>
  );
}

export default function AllPositionsPanel() {
  const [positions, setPositions] = useState<OpenPosition[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("unrealized_pnl");
  const [sortAsc, setSortAsc] = useState(true);

  useEffect(() => {
    const load = () => api.openPositions().then(setPositions).catch(() => {});
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((p) => !p);
    else { setSortKey(key); setSortAsc(true); }
  };

  const sorted = [...positions].sort((a, b) => {
    const va = a[sortKey] as string | number;
    const vb = b[sortKey] as string | number;
    if (typeof va === "string" && typeof vb === "string")
      return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? (va as number) - (vb as number) : (vb as number) - (va as number);
  });

  const totalUnrealized = positions.reduce((s, p) => s + p.unrealized_pnl, 0);
  const totalMargin = positions.reduce((s, p) => s + p.margin, 0);

  if (positions.length === 0) {
    return (
      <div className="bg-[#161b27] rounded-xl border border-[#1e2636] p-8 text-center text-gray-600 text-sm">
        目前無開倉持倉
      </div>
    );
  }

  return (
    <div className="bg-[#161b27] rounded-xl border border-[#1e2636] overflow-hidden">
      {/* Summary bar */}
      <div className="flex items-center gap-6 px-4 py-3 border-b border-[#1e2636]">
        <span className="text-gray-500 text-[11px] uppercase tracking-wider">
          全部持倉（{positions.length}）
        </span>
        <span className="text-[11px]">
          <span className="text-gray-500">浮動合計 </span>
          <span className={`font-semibold ${totalUnrealized >= 0 ? "text-green-400" : "text-red-400"}`}>
            {totalUnrealized >= 0 ? "+" : ""}${totalUnrealized.toFixed(0)}
          </span>
        </span>
        <span className="text-[11px]">
          <span className="text-gray-500">保證金合計 </span>
          <span className="text-yellow-400 font-semibold">${totalMargin.toFixed(0)}</span>
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-[#0f1117]">
            <tr>
              <Th label="分析師" sortBy="analyst_name" active={sortKey === "analyst_name"} asc={sortAsc} onSort={() => handleSort("analyst_name")} />
              <Th label="幣種" sortBy="symbol" active={sortKey === "symbol"} asc={sortAsc} onSort={() => handleSort("symbol")} />
              <Th label="方向" />
              <Th label="槓桿" />
              <Th label="進場價" />
              <Th label="現價" />
              <Th label="倉位" />
              <Th label="保證金" sortBy="margin" active={sortKey === "margin"} asc={sortAsc} onSort={() => handleSort("margin")} />
              <Th label="浮動盈虧" sortBy="unrealized_pnl" active={sortKey === "unrealized_pnl"} asc={sortAsc} onSort={() => handleSort("unrealized_pnl")} />
              <Th label="SL / TP" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e2636]">
            {sorted.map((p) => {
              const priceDiff =
                p.current_price && p.entry_price
                  ? ((p.current_price - p.entry_price) / p.entry_price) * 100
                  : 0;
              return (
                <tr key={p.id} className="hover:bg-[#0f1117] transition-colors">
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <div
                        className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[9px] font-bold shrink-0"
                        style={{ backgroundColor: p.analyst_color }}
                      >
                        {p.analyst_name.split(" ").map((n) => n[0]).join("")}
                      </div>
                      <span className="text-gray-300 truncate max-w-[80px]">{p.analyst_name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-gray-200 font-medium">{p.symbol}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        p.side === "long"
                          ? "bg-green-950 text-green-400"
                          : "bg-red-950 text-red-400"
                      }`}
                    >
                      {p.side === "long" ? "LONG" : "SHORT"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-400">×{p.leverage}</td>
                  <td className="px-3 py-2 text-gray-400">
                    ${p.entry_price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-gray-300">
                      ${p.current_price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                    </span>
                    <span className={`ml-1 text-[10px] ${priceDiff >= 0 ? "text-green-500" : "text-red-500"}`}>
                      {priceDiff >= 0 ? "+" : ""}{priceDiff.toFixed(2)}%
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-400">${p.quantity.toFixed(0)}</td>
                  <td className="px-3 py-2 text-yellow-400">${p.margin.toFixed(0)}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`font-semibold ${
                        p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(2)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-600 text-[10px]">
                    {p.stop_loss
                      ? `$${p.stop_loss.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
                      : "—"}{" "}
                    /{" "}
                    {p.take_profit
                      ? `$${p.take_profit.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
