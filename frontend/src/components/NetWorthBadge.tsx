'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { Wallet } from '@/lib/types';

interface Props {
  wallet: Wallet | null;
  loading: boolean;
}

export default function NetWorthBadge({ wallet, loading }: Props) {
  const [showDropdown, setShowDropdown] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F5F5F5] rounded-full animate-pulse">
        <span className="text-sm">🪙</span>
        <span className="text-xs text-[#C8C8C8]">...</span>
      </div>
    );
  }

  if (!wallet) {
    return (
      <button
        onClick={() => {
          // Init wallet on click
          const id = localStorage.getItem('arena_user_id') || crypto.randomUUID();
          localStorage.setItem('arena_user_id', id);
          fetch(`/api/wallet/${id}`).then(() => window.location.reload());
        }}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FFF8E1] rounded-full hover:bg-[#FFE082] transition-colors"
      >
        <span className="text-sm">💰</span>
        <span className="text-xs text-[#F57C00] font-medium">领取 200 积分</span>
      </button>
    );
  }

  const isProfit = wallet.total_pnl >= 0;
  const netWorth = wallet.net_worth;
  const activeHoldings = wallet.holdings.filter((h) => h.status === 'active').length;

  return (
    <div className="relative">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border transition-all hover:shadow-sm ${
          isProfit
            ? 'bg-[#F0FFF4] border-[#C8E6C9] text-[#2E7D32]'
            : wallet.total_pnl < 0
              ? 'bg-[#FFF5F5] border-[#FFCDD2] text-[#C62828]'
              : 'bg-[#FFF8E1] border-[#FFE082] text-[#F57C00]'
        }`}
      >
        <span className="text-sm">💰</span>
        <span className="text-xs font-bold tabular-nums">{netWorth.toLocaleString()}</span>
        <span className="text-[10px] opacity-70">积分</span>
        {wallet.total_pnl !== 0 && (
          <span className={`text-[10px] font-medium ${isProfit ? 'text-[#00C853]' : 'text-[#FF1744]'}`}>
            {isProfit ? '↑' : '↓'}{Math.abs(wallet.total_pnl)}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {showDropdown && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowDropdown(false)} />
          <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl border border-[#EBEBEB] shadow-lg z-50 overflow-hidden animate-slide-down">
            <div className="p-4 border-b border-[#F0F0F0]">
              <div className="text-xs text-[#8590A6] mb-1">观点身价</div>
              <div className="text-2xl font-bold text-[#1A1A1A] tabular-nums">
                {netWorth.toLocaleString()} <span className="text-sm font-normal text-[#8590A6]">积分</span>
              </div>
            </div>

            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#8590A6]">可用余额</span>
                <span className="font-medium tabular-nums">{wallet.balance.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#8590A6]">持仓市值</span>
                <span className="font-medium tabular-nums">{(netWorth - wallet.balance).toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#8590A6]">总盈亏</span>
                <span className={`font-bold tabular-nums ${isProfit ? 'text-[#00C853]' : 'text-[#FF1744]'}`}>
                  {isProfit ? '+' : ''}{wallet.total_pnl}
                </span>
              </div>
              {activeHoldings > 0 && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[#8590A6]">持仓观点</span>
                  <span className="font-medium">{activeHoldings} 个</span>
                </div>
              )}
            </div>

            <Link
              href="/portfolio"
              onClick={() => setShowDropdown(false)}
              className="block px-4 py-3 text-center text-sm text-[#0066FF] font-medium border-t border-[#F0F0F0] hover:bg-[#F5F5F5] transition-colors"
            >
              查看我的持仓 →
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
