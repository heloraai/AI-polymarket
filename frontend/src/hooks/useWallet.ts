'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Wallet } from '@/lib/types';

export function useWallet() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [loading, setLoading] = useState(true);

  const userId = typeof window !== 'undefined'
    ? localStorage.getItem('arena_user_id')
    : null;

  const refresh = useCallback(async () => {
    if (!userId) { setLoading(false); return; }
    try {
      const res = await fetch(`/api/wallet/${userId}`);
      if (res.ok) {
        setWallet(await res.json());
      }
    } catch {
      console.error('Failed to fetch wallet');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const buyShares = useCallback(async (
    debateId: string,
    optionKey: string,
    quantity: number = 1,
  ) => {
    if (!userId) throw new Error('Not logged in');
    const res = await fetch(`/api/wallet/${userId}/buy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        debate_id: debateId,
        option_key: optionKey,
        quantity,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Buy failed');
    }
    const data = await res.json();
    setWallet(data.wallet);
    return data;
  }, [userId]);

  const initWallet = useCallback(async () => {
    if (typeof window === 'undefined') return;
    let id = localStorage.getItem('arena_user_id');
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem('arena_user_id', id);
    }
    try {
      const res = await fetch(`/api/wallet/${id}`);
      if (res.ok) {
        setWallet(await res.json());
      }
    } catch {
      console.error('Failed to init wallet');
    }
  }, []);

  return { wallet, loading, refresh, buyShares, initWallet, userId };
}
