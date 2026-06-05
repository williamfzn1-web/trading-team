"use client";

import { useEffect, useState } from "react";
import { Analyst, AnalystRiskStatus, EquityPoint, PriceTick, WSPayload } from "@/lib/types";
import { api } from "@/lib/api";
import { socket } from "@/lib/websocket";
import PriceTicker from "@/components/PriceTicker";
import OverviewPanel from "@/components/OverviewPanel";
import AnalystCard from "@/components/AnalystCard";
import AnalystModal from "@/components/AnalystModal";
import GroupChat from "@/components/GroupChat";
import RiskPanel from "@/components/RiskPanel";
import PaperTradingPanel from "@/components/PaperTradingPanel";
import ShadowPanel from "@/components/ShadowPanel";
import PageNav from "@/components/PageNav";
import AllPositionsPanel from "@/components/AllPositionsPanel";
import LeaderboardPanel from "@/components/LeaderboardPanel";
import CorrelationPanel from "@/components/CorrelationPanel";
import PnLCalendarPanel from "@/components/PnLCalendarPanel";

type AnalyticsTab = "positions" | "leaderboard" | "correlation" | "calendar";

export default function Dashboard() {
  const [analysts, setAnalysts] = useState<Analyst[]>([]);
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [selected, setSelected] = useState<Analyst | null>(null);
  const [connected, setConnected] = useState(false);
  const [riskMap, setRiskMap] = useState<Map<number, AnalystRiskStatus>>(new Map());
  const [activeTab, setActiveTab] = useState<AnalyticsTab>("positions");

  useEffect(() => {
    api.accounts().then(setAnalysts).catch(() => {});
    api.combinedEquity().then(setEquity).catch(() => {});
    api.prices().then(setPrices).catch(() => {});
  }, []);

  useEffect(() => {
    const loadRisk = () =>
      api.riskStatus().then((r) => {
        setRiskMap(new Map(r.analysts.map((a) => [a.id, a])));
      }).catch(() => {});
    loadRisk();
    const id = setInterval(loadRisk, 10_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const off = socket.on((data: WSPayload) => {
      if (data.type === "update") {
        setPrices(data.prices);
        setAnalysts(data.accounts);
        setConnected(true);
      }
    });
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsUrl = apiUrl.replace(/^http/, "ws") + "/ws";
    socket.connect(wsUrl);
    return () => {
      off();
      socket.disconnect();
    };
  }, []);

  const sorted = [...analysts].sort((a, b) => b.total_pnl - a.total_pnl);

  const handleTogglePause = async (analystId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.togglePause(analystId);
      api.riskStatus().then((r) =>
        setRiskMap(new Map(r.analysts.map((a) => [a.id, a])))
      ).catch(() => {});
    } catch {}
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-white">
      <PriceTicker prices={prices} />

      <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e2636]">
        <div>
          <h1 className="text-base font-bold text-white tracking-tight">
            加密合約交易平台
          </h1>
          <p className="text-gray-600 text-xs">
            {analysts.length} 位量化分析師 · Paper Trading · 多策略
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-gray-600"}`}
          />
          <span className="text-[11px] text-gray-500">
            {connected ? "即時連線" : "連線中..."}
          </span>
        </div>
      </div>

      <PageNav />

      <OverviewPanel analysts={analysts} equity={equity} />

      <div className="px-5 pt-5">
        <RiskPanel />
        <PaperTradingPanel />
        <ShadowPanel />
      </div>

      <div className="px-5 pb-2">
        <div className="flex gap-1 border-b border-[#1e2636] mb-4">
          {(
            [
              { key: "positions", label: "全部持倉" },
              { key: "leaderboard", label: "績效排行" },
              { key: "correlation", label: "相關性矩陣" },
              { key: "calendar", label: "P&L 日曆" },
            ] as { key: AnalyticsTab; label: string }[]
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium transition-colors rounded-t-lg border-b-2 ${
                activeTab === tab.key
                  ? "text-white border-indigo-500"
                  : "text-gray-500 border-transparent hover:text-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {activeTab === "positions" && <AllPositionsPanel />}
        {activeTab === "leaderboard" && <LeaderboardPanel analysts={analysts} />}
        {activeTab === "correlation" && <CorrelationPanel />}
        {activeTab === "calendar" && <PnLCalendarPanel />}
      </div>

      <div className="px-5 pb-8 grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5">
        <div>
          <p className="text-gray-500 text-[11px] uppercase tracking-widest mb-3">
            分析師帳戶（按盈虧排序）
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-3">
            {sorted.map((a) => {
              const riskInfo = riskMap.get(a.id);
              const isPaused = riskInfo ? !riskInfo.can_trade : false;
              return (
                <AnalystCard
                  key={a.id}
                  analyst={a}
                  onClick={() => setSelected(a)}
                  isPaused={isPaused}
                  sizeMultiplier={riskInfo?.size_multiplier}
                  onTogglePause={(e) => handleTogglePause(a.id, e)}
                />
              );
            })}
          </div>
        </div>

        <div>
          <p className="text-gray-500 text-[11px] uppercase tracking-widest mb-3">
            群組討論
          </p>
          <GroupChat />
        </div>
      </div>

      {selected && (
        <AnalystModal analyst={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
