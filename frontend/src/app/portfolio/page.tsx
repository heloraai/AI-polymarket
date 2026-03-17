'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { Holding } from '@/lib/types';
import { useWallet } from '@/hooks/useWallet';

export default function PortfolioPage() {
  const { wallet, loading } = useWallet();
  const [portfolio, setPortfolio] = useState<{ active: Holding[]; settled: Holding[]; summary: Record<string, number> } | null>(null);

  useEffect(() => {
    const userId = localStorage.getItem('arena_user_id');
    if (!userId) return;
    fetch(`/api/wallet/${userId}/portfolio`)
      .then((r) => r.json())
      .then(setPortfolio)
      .catch(console.error);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F6F6F6]">
        <div className="text-[#8590A6] text-sm">加载中...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F6F6F6]">
      {/* Header */}
      <header className="bg-white border-b border-[#EBEBEB] sticky top-0 z-50">
        <div className="max-w-3xl mx-auto px-4 md:px-6 h-14 flex items-center gap-4">
          <Link href="/" className="text-[#8590A6] hover:text-[#1A1A1A] transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </Link>
          <h1 className="text-base font-semibold text-[#1A1A1A]">我的观点持仓</h1>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 md:px-6 py-6 space-y-4">
        {/* Summary card */}
        {wallet && (
          <div className="bg-white rounded-xl border border-[#EBEBEB] p-5">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-[#8590A6] mb-1">观点身价</div>
                <div className="text-xl font-bold text-[#1A1A1A] tabular-nums">{wallet.net_worth.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-[#8590A6] mb-1">可用余额</div>
                <div className="text-xl font-bold text-[#1A1A1A] tabular-nums">{wallet.balance.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-[#8590A6] mb-1">总盈亏</div>
                <div className={`text-xl font-bold tabular-nums ${wallet.total_pnl >= 0 ? 'text-[#00C853]' : 'text-[#FF1744]'}`}>
                  {wallet.total_pnl >= 0 ? '+' : ''}{wallet.total_pnl}
                </div>
              </div>
              <div>
                <div className="text-xs text-[#8590A6] mb-1">持仓数</div>
                <div className="text-xl font-bold text-[#1A1A1A]">
                  {wallet.holdings.filter((h) => h.status === 'active').length}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Active holdings */}
        {portfolio && portfolio.active.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-[#1A1A1A] mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#0066FF]" />
              持仓中
            </h2>
            <div className="space-y-2">
              {portfolio.active.map((h) => (
                <Link key={h.id} href={`/debate/${h.debate_id}`} className="block">
                  <div className="bg-white rounded-xl border border-[#EBEBEB] p-4 hover:shadow-sm transition-all">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-[#1A1A1A] truncate flex-1">{h.debate_title}</span>
                      <span className={`text-sm font-bold tabular-nums ml-2 ${(h.pnl ?? 0) >= 0 ? 'text-[#00C853]' : 'text-[#FF1744]'}`}>
                        {(h.pnl ?? 0) >= 0 ? '+' : ''}{h.pnl ?? 0}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-[#8590A6]">
                      <span className="px-2 py-0.5 rounded bg-[#E8F0FE] text-[#0066FF] font-medium">{h.option_label}</span>
                      <span>{h.quantity}股 · 买入价 {h.buy_price}分 · 现价 {h.current_price ?? '-'}分</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Settled holdings */}
        {portfolio && portfolio.settled.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-[#1A1A1A] mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#8590A6]" />
              已结算
            </h2>
            <div className="space-y-2">
              {portfolio.settled.map((h) => {
                const isWin = h.result === 'win';
                return (
                  <Link key={h.id} href={`/debate/${h.debate_id}`} className="block">
                    <div className={`rounded-xl border p-4 ${isWin ? 'bg-[#F1FFF6] border-[#C8E6C9]' : 'bg-[#FFF5F5] border-[#FFCDD2]'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-[#1A1A1A] truncate flex-1">{h.debate_title}</span>
                        <span className={`text-sm font-bold tabular-nums ml-2 ${isWin ? 'text-[#00C853]' : 'text-[#FF1744]'}`}>
                          {isWin ? '+' : ''}{h.pnl ?? 0}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs text-[#8590A6]">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded font-medium ${isWin ? 'bg-[#E8F5E9] text-[#2E7D32]' : 'bg-[#FFEBEE] text-[#C62828]'}`}>
                            {isWin ? '\u2713 ' : '\u2717 '}{h.option_label}
                          </span>
                        </div>
                        <span>{h.quantity}股 · 买入价 {h.buy_price}分</span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty state */}
        {portfolio && portfolio.active.length === 0 && portfolio.settled.length === 0 && (
          <div className="bg-white rounded-xl border border-[#EBEBEB] p-12 text-center">
            <div className="text-4xl mb-3">📊</div>
            <p className="text-[#8590A6] text-sm">你还没有买入任何观点</p>
            <Link href="/" className="inline-block mt-3 px-4 py-2 bg-[#0066FF] text-white text-sm rounded-full hover:bg-[#0052CC] transition-all">
              去热榜看看 →
            </Link>
          </div>
        )}

        {/* Transaction history */}
        {wallet && wallet.transactions.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-[#1A1A1A] mb-2">交易记录</h2>
            <div className="bg-white rounded-xl border border-[#EBEBEB] overflow-hidden">
              {wallet.transactions.slice().reverse().slice(0, 20).map((tx) => (
                <div key={tx.id} className="px-4 py-3 border-b border-[#F0F0F0] last:border-0 flex items-center justify-between">
                  <div>
                    <div className="text-sm text-[#1A1A1A]">
                      {tx.type === 'buy' ? '买入' : tx.type === 'settle_win' ? '结算收益' : '结算亏损'}
                      <span className="text-[#8590A6] ml-1">「{tx.option_label}」</span>
                    </div>
                    <div className="text-[10px] text-[#C8C8C8] mt-0.5">
                      {tx.shares}股 × {tx.price_per_share}分
                    </div>
                  </div>
                  <span className={`text-sm font-bold tabular-nums ${tx.amount >= 0 ? 'text-[#00C853]' : 'text-[#FF1744]'}`}>
                    {tx.amount >= 0 ? '+' : ''}{tx.amount}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
