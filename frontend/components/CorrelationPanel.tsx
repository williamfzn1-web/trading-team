"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CorrelationData } from "@/lib/types";

function cellColor(v: number, isDiag: boolean): string {
  if (isDiag) return "bg-[#1e2636] text-gray-500";
  if (v >= 0.7) return "bg-red-700 text-red-100";
  if (v >= 0.4) return "bg-red-900 text-red-300";
  if (v >= 0.1) return "bg-[#1e2636] text-gray-400";
  if (v >= -0.1) return "bg-[#0f1117] text-gray-500";
  if (v >= -0.4) return "bg-blue-950 text-blue-300";
  return "bg-blue-800 text-blue-100";
}

function initials(name: string) {
  return name.split(" ").map((n) => n[0]).join("");
}

export default function CorrelationPanel() {
  const [data, setData] = useState<CorrelationData | null>(null);

  useEffect(() => {
    api.correlation().then(setData).catch(() => {});
  }, []);

  if (!data || data.analysts.length === 0) {
    return (
      <div className="bg-[#161b27] rounded-xl border border-[#1e2636] p-8 text-center text-gray-600 text-sm">
        資料不足，無法計算相關性（需要更多歷史快照）
      </div>
    );
  }

  return (
    <div className="bg-[#161b27] rounded-xl border border-[#1e2636] overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-[#1e2636]">
        <span className="text-gray-500 text-[11px] uppercase tracking-wider">
          策略相關性矩陣
        </span>
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-blue-800 inline-block" />
            負相關（分散好）
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#1e2636] inline-block" />
            不相關
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-red-700 inline-block" />
            正相關（集中風險）
          </span>
        </div>
      </div>

      <div className="p-4 overflow-x-auto">
        <table className="text-[10px] border-collapse">
          <thead>
            <tr>
              <th className="w-20" />
              {data.analysts.map((a) => (
                <th key={a.id} className="px-0.5 py-0.5 text-center" style={{ width: 36 }}>
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[8px] font-bold mx-auto"
                    style={{ backgroundColor: a.color }}
                    title={`${a.name} — ${a.strategy}`}
                  >
                    {initials(a.name)}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.analysts.map((row, i) => (
              <tr key={row.id}>
                <td className="pr-2 py-0.5">
                  <div className="flex items-center gap-1">
                    <div
                      className="w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: row.color }}
                    />
                    <span className="text-gray-400 truncate max-w-[64px]" title={row.name}>
                      {row.name.split(" ")[0]}
                    </span>
                  </div>
                </td>
                {data.matrix[i].map((val, j) => (
                  <td key={j} className="px-0.5 py-0.5">
                    <div
                      className={`w-8 h-7 rounded flex items-center justify-center text-[9px] font-medium ${cellColor(val, i === j)}`}
                      title={i === j ? row.name : `${row.name} × ${data.analysts[j].name}: ${val.toFixed(3)}`}
                    >
                      {i === j ? "—" : val.toFixed(2)}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
