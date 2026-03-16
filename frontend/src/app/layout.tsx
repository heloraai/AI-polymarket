import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "观点交易所 — 观点有价，下注见真章",
  description: "知乎热榜上最吵的问题，交给 AI 来辩。5 个 AI 圆桌讨论、亮牌下注、站队辩护，刘看山一锤定音。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
