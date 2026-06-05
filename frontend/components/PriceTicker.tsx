"use client";

import { PriceTick } from "@/lib/types";

const DISPLAY = [
  "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
  "XRP/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT",
];

function fmt(price: number) {
  if (price >= 1000) return price.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (price >= 1) return price.toFixed(2);
  return price.toFixed(4);
}

export default function PriceTicker({ prices }: { prices: Record<string, PriceTick> }) {
  return (
    <div className="bg-[#0a0d14] border-b border-[#1e2636] sticky top-0 z-50">
      <div className="flex gap-6 px-4 py-2 overflow-x-auto scrollbar-hide">
        {DISPLAY.map((sym) => {
          const d = prices[sym];
          const base = sym.split("/")[0];
          const up = d ? d.change_24h >= 0 : true;
          return (
            <div key={sym} className="flex items-center gap-2 whitespace-nowrap shrink-0">
              <span className="text-gray-500 text-xs font-semibold tracking-wider">{base}</span>
              <span className="text-white text-sm font-bold">
                {d ? `$${fmt(d.price)}` : "—"}
              </span>
              <span className={`text-xs font-medium ${up ? "text-green-400" : "text-red-400"}`}>
                {d ? `${up ? "+" : ""}${d.change_24h.toFixed(2)}%` : ""}
              </span>
            </div>
          );
        })}
        <div className="ml-auto flex items-center shrink-0">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest">LIVE · Binance</span>
        </div>
      </div>
    </div>
  );
}
