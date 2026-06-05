"use client";

import { useEffect, useRef, useState } from "react";
import { GroupMessage } from "@/lib/types";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/time";

const TYPE_BADGE: Record<string, string> = {
  signal: "bg-blue-900 text-blue-300",
  alert: "bg-red-900 text-red-300",
  analysis: "bg-[#1e2636] text-gray-400",
};

export default function GroupChat() {
  const [msgs, setMsgs] = useState<GroupMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.messages().then(setMsgs).catch(() => {});
    const id = setInterval(
      () => api.messages().then(setMsgs).catch(() => {}),
      10_000,
    );
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [msgs]);

  return (
    <div className="bg-[#161b27] rounded-xl border border-[#1e2636] flex flex-col h-full max-h-[500px]">
      <div className="px-4 py-3 border-b border-[#1e2636] flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        <p className="text-gray-300 text-sm font-semibold">分析師討論群組</p>
        <span className="ml-auto text-[10px] text-gray-600">{msgs.length} 則訊息</span>
      </div>

      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 scrollbar-hide">
        {msgs.length === 0 && (
          <p className="text-gray-600 text-sm text-center pt-8">
            尚無訊息 — Phase 2 加入 AI 後自動生成分析
          </p>
        )}
        {msgs.map((m) => (
          <div key={m.id} className="flex gap-2.5">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[9px] font-bold shrink-0 mt-0.5"
              style={{ backgroundColor: m.analyst_color }}
            >
              {m.analyst_name
                .split(" ")
                .map((n) => n[0])
                .join("")}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                <span className="text-[11px] text-white font-semibold">
                  {m.analyst_name}
                </span>
                <span className="text-[9px]" style={{ color: m.analyst_color }}>
                  {m.strategy}
                </span>
                <span
                  className={`text-[9px] px-1.5 py-0.5 rounded ${TYPE_BADGE[m.message_type] ?? TYPE_BADGE.analysis}`}
                >
                  {m.message_type}
                </span>
                <span className="text-[10px] text-gray-600 ml-auto shrink-0">
                  {timeAgo(m.timestamp)}
                </span>
              </div>
              <p className="text-gray-300 text-xs leading-relaxed">{m.content}</p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
