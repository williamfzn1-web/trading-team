import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "加密合約交易平台",
  description: "10 位量化分析師 · 多策略 · 即時追蹤",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
