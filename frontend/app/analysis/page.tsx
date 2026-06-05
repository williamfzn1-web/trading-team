"use client";

import { useEffect, useState } from "react";
import { PriceTick } from "@/lib/types";
import { api } from "@/lib/api";
import PriceTicker from "@/components/PriceTicker";
import PageNav from "@/components/PageNav";
import WalkForwardPanel from "@/components/WalkForwardPanel";
import MonteCarloPanel from "@/components/MonteCarloPanel";
import BacktestPanel from "@/components/BacktestPanel";

export default function AnalysisPage() {
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});

  useEffect(() => {
    api.prices().then(setPrices).catch(() => {});
    const id = setInterval(() => api.prices().then(setPrices).catch(() => {}), 15_000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="min-h-screen bg-[#0f1117] text-white">
      <PriceTicker prices={prices} />

      {/* Top nav */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e2636]">
        <div>
          <h1 className="text-base font-bold text-white tracking-tight">回測分析中心</h1>
          <p className="text-gray-600 text-xs">Walk-Forward · Monte Carlo · 歷史回測</p>
        </div>
      </div>

      <PageNav />

      <div className="px-5 pt-5 pb-10">
        <WalkForwardPanel />
        <MonteCarloPanel />
        <BacktestPanel />
      </div>
    </div>
  );
}
