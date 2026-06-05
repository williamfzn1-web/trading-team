"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DailyPnL } from "@/lib/types";

const DAY_HEADERS = ["日", "一", "二", "三", "四", "五", "六"];

function cellBg(pnl: number | null): string {
  if (pnl === null) return "";
  if (pnl === 0) return "bg-[#1e2636]";
  if (pnl > 0) {
    if (pnl > 500) return "bg-green-500/30 border-green-500/50";
    if (pnl > 200) return "bg-green-700/30 border-green-700/50";
    return "bg-green-900/30 border-green-900/50";
  }
  if (pnl < -500) return "bg-red-500/30 border-red-500/50";
  if (pnl < -200) return "bg-red-700/30 border-red-700/50";
  return "bg-red-900/30 border-red-900/50";
}

function cellText(pnl: number | null): string {
  if (pnl === null) return "text-gray-700";
  if (pnl > 0) return "text-green-400";
  if (pnl < 0) return "text-red-400";
  return "text-gray-500";
}

export default function PnLCalendarPanel() {
  const [data, setData] = useState<DailyPnL[]>([]);
  const [viewDate, setViewDate] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() };
  });

  useEffect(() => {
    api.dailyPnL().then(setData).catch(() => {});
  }, []);

  const pnlMap = new Map(data.map((d) => [d.date, d.pnl]));

  const { year, month } = viewDate;
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];

  // Build calendar grid (6 rows × 7 cols)
  const cells: (number | null)[] = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const monthName = new Date(year, month).toLocaleDateString("zh-TW", {
    year: "numeric",
    month: "long",
  });

  const prevMonth = () =>
    setViewDate(({ year, month }) =>
      month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 }
    );
  const nextMonth = () =>
    setViewDate(({ year, month }) =>
      month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 }
    );

  const monthData = data.filter((d) => {
    const [y, m] = d.date.split("-").map(Number);
    return y === year && m - 1 === month;
  });
  const monthPnl = monthData.reduce((s, d) => s + d.pnl, 0);
  const winDays = monthData.filter((d) => d.pnl > 0).length;
  const lossDays = monthData.filter((d) => d.pnl < 0).length;

  return (
    <div className="bg-[#161b27] rounded-xl border border-[#1e2636] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e2636]">
        <div className="flex items-center gap-4">
          <span className="text-gray-500 text-[11px] uppercase tracking-wider">每日 P&L 日曆</span>
          <span className="text-[11px]">
            <span className="text-gray-500">本月 </span>
            <span className={`font-semibold ${monthPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {monthPnl >= 0 ? "+" : ""}${monthPnl.toFixed(0)}
            </span>
          </span>
          <span className="text-[11px] text-gray-500">
            獲利 <span className="text-green-400 font-medium">{winDays}天</span>
            {" / "}
            虧損 <span className="text-red-400 font-medium">{lossDays}天</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={prevMonth}
            className="text-gray-500 hover:text-white px-2 py-0.5 rounded hover:bg-[#1e2636] transition-colors text-sm"
          >
            ‹
          </button>
          <span className="text-white text-sm font-medium w-28 text-center">{monthName}</span>
          <button
            onClick={nextMonth}
            className="text-gray-500 hover:text-white px-2 py-0.5 rounded hover:bg-[#1e2636] transition-colors text-sm"
          >
            ›
          </button>
        </div>
      </div>

      {/* Calendar */}
      <div className="p-3">
        {/* Day headers */}
        <div className="grid grid-cols-7 mb-1">
          {DAY_HEADERS.map((d) => (
            <div key={d} className="text-center text-[10px] text-gray-600 py-1 font-medium">
              {d}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7 gap-1">
          {cells.map((day, i) => {
            if (day === null) {
              return <div key={i} className="h-16" />;
            }
            const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const pnl = pnlMap.has(dateStr) ? pnlMap.get(dateStr)! : null;
            const isToday = dateStr === todayStr;
            const isFuture = dateStr > todayStr;

            return (
              <div
                key={i}
                className={`h-16 rounded-lg border p-1.5 flex flex-col ${
                  isFuture
                    ? "border-transparent opacity-30"
                    : pnl !== null
                    ? `${cellBg(pnl)} border`
                    : "border-[#1e2636]"
                } ${isToday ? "ring-1 ring-indigo-500" : ""}`}
              >
                <span
                  className={`text-[10px] font-semibold ${
                    isToday ? "text-indigo-400" : "text-gray-500"
                  }`}
                >
                  {day}
                </span>
                {pnl !== null && (
                  <span
                    className={`text-[11px] font-bold mt-auto leading-none ${cellText(pnl)}`}
                  >
                    {pnl >= 0 ? "+" : ""}
                    {Math.abs(pnl) >= 1000
                      ? `$${(pnl / 1000).toFixed(1)}k`
                      : `$${pnl.toFixed(0)}`}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
