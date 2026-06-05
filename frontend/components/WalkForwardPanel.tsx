"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { WalkForwardRun, WFWindow } from "@/lib/types";

function ConsistencyBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const [label, color] =
    score >= 0.7  ? ["穩健", "bg-green-900/60 text-green-300"] :
    score >= 0.3  ? ["中等", "bg-yellow-900/60 text-yellow-300"] :
    score >= 0    ? ["偏弱", "bg-orange-900/60 text-orange-300"] :
                    ["反轉", "bg-red-900/60 text-red-400"];
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${color}`}>
      {label} {pct}%
    </span>
  );
}

function WindowRow({ w }: { w: WFWindow }) {
  const sign = (n: number) => (n >= 0 ? "+" : "");
  const retColor = (n: number) => n >= 0 ? "text-green-400" : "text-red-400";
  return (
    <tr className="border-b border-[#1a2030] hover:bg-[#1a2030] transition-colors text-[11px]">
      <td className="px-3 py-2 text-gray-500 whitespace-nowrap">W{w.window}</td>
      <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{w.train_start} → {w.train_end}</td>
      <td className={`px-3 py-2 font-semibold ${retColor(w.train.return_pct)}`}>{sign(w.train.return_pct)}{w.train.return_pct.toFixed(1)}%</td>
      <td className="px-3 py-2 text-gray-400">{w.train.win_rate.toFixed(0)}%</td>
      <td className="px-3 py-2 text-gray-400">{w.train.sharpe.toFixed(2)}</td>
      <td className="px-3 py-2 text-gray-500">{w.train.trades}</td>
      <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{w.test_start} → {w.test_end}</td>
      <td className={`px-3 py-2 font-semibold ${retColor(w.test.return_pct)}`}>{sign(w.test.return_pct)}{w.test.return_pct.toFixed(1)}%</td>
      <td className="px-3 py-2 text-gray-400">{w.test.win_rate.toFixed(0)}%</td>
      <td className="px-3 py-2 text-gray-400">{w.test.sharpe.toFixed(2)}</td>
      <td className="px-3 py-2 text-gray-500">{w.test.trades}</td>
      <td className="px-3 py-2"><ConsistencyBadge score={w.consistency} /></td>
    </tr>
  );
}

export default function WalkForwardPanel() {
  const [runs, setRuns] = useState<WalkForwardRun[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [windows, setWindows] = useState<WFWindow[]>([]);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<Record<string, number>>({});
  const [open, setOpen] = useState(true);

  const loadRuns = useCallback(() => {
    api.walkForwardLatest().then(setRuns).catch(() => {});
    api.walkForwardStatus().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    loadRuns();
    const id = setInterval(loadRuns, 10_000);
    return () => clearInterval(id);
  }, [loadRuns]);

  useEffect(() => {
    if (selected) api.walkForwardWindows(selected).then(setWindows).catch(() => {});
    else setWindows([]);
  }, [selected]);

  const handleRun = async () => {
    setRunning(true);
    try {
      await api.walkForwardRun(120, 60, 60);
      setTimeout(loadRuns, 2000);
    } finally {
      setRunning(false);
    }
  };

  const isRunning = (status.running ?? 0) > 0 || (status.pending ?? 0) > 0;
  const selectedRun = runs.find(r => r.id === selected);

  return (
    <div className="mb-5 bg-[#131924] rounded-xl border border-[#1e2636] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e2636]">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <div className={`w-2 h-2 rounded-full ${isRunning ? "bg-yellow-400 animate-pulse" : "bg-blue-400"}`} />
          <span className="text-sm font-semibold text-white">Walk-Forward 驗證</span>
          <span className="text-[10px] text-gray-500 bg-[#1e2636] px-2 py-0.5 rounded-full">
            訓練 120d · 測試 60d · 步進 60d
          </span>
          <span className="text-gray-600 text-xs ml-1">{open ? "▲" : "▼"}</span>
        </button>
        <button
          onClick={handleRun}
          disabled={running || isRunning}
          className="text-[11px] text-gray-400 hover:text-blue-300 transition-colors px-3 py-1 rounded-md border border-[#1e2636] hover:border-blue-800 disabled:opacity-40"
        >
          {isRunning ? `執行中 (${(status.running ?? 0) + (status.pending ?? 0)} 個)` : running ? "啟動中..." : "執行驗證"}
        </button>
      </div>

      {open && (
        runs.length === 0 ? (
          <p className="text-gray-600 text-sm text-center py-8">
            尚未執行 — 點擊「執行驗證」開始（約需 2–3 分鐘）
          </p>
        ) : (
          <>
            {/* Strategy summary table */}
            <div className="overflow-x-auto border-b border-[#1e2636]">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-gray-500 uppercase text-[10px] border-b border-[#1e2636]">
                    {["策略", "窗口數", "平均一致性", "詳細"].map(h => (
                      <th key={h} className="px-4 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.map(r => (
                    <tr key={r.id} className="border-b border-[#1a2030] hover:bg-[#1a2030] transition-colors">
                      <td className="px-4 py-2 text-white font-medium">{r.strategy}</td>
                      <td className="px-4 py-2 text-gray-400">{r.n_windows}</td>
                      <td className="px-4 py-2"><ConsistencyBadge score={r.avg_consistency} /></td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() => setSelected(selected === r.id ? null : r.id)}
                          className="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors"
                        >
                          {selected === r.id ? "收起" : "展開"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Window detail */}
            {selected && windows.length > 0 && (
              <div className="overflow-x-auto max-h-72 overflow-y-auto">
                <div className="px-4 py-2 text-[10px] text-gray-500 border-b border-[#1e2636]">
                  {selectedRun?.strategy} — 各窗口明細
                </div>
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="text-gray-500 uppercase text-[10px] border-b border-[#1e2636] sticky top-0 bg-[#131924]">
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left whitespace-nowrap">訓練期</th>
                      <th className="px-3 py-2 text-left">報酬</th>
                      <th className="px-3 py-2 text-left">勝率</th>
                      <th className="px-3 py-2 text-left">Sharpe</th>
                      <th className="px-3 py-2 text-left">筆數</th>
                      <th className="px-3 py-2 text-left whitespace-nowrap">測試期</th>
                      <th className="px-3 py-2 text-left">報酬</th>
                      <th className="px-3 py-2 text-left">勝率</th>
                      <th className="px-3 py-2 text-left">Sharpe</th>
                      <th className="px-3 py-2 text-left">筆數</th>
                      <th className="px-3 py-2 text-left">一致性</th>
                    </tr>
                  </thead>
                  <tbody>
                    {windows.map(w => <WindowRow key={w.window} w={w} />)}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )
      )}
    </div>
  );
}
