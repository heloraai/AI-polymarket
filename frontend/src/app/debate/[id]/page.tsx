'use client';

import { useEffect, useState, use } from 'react';
import Link from 'next/link';
import RoundtableComment from '@/components/RoundtableComment';
import BettingPanel from '@/components/BettingPanel';
import VictoryPoster from '@/components/VictoryPoster';
import { getAgent } from '@/lib/constants';
import type { Debate, Message } from '@/lib/types';
import { useWallet } from '@/hooks/useWallet';

function decodeHtmlEntities(text: string): string {
  const textarea = typeof document !== 'undefined' ? document.createElement('textarea') : null;
  if (!textarea) return text.replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n))).replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
  textarea.innerHTML = text;
  return textarea.value;
}

function DescriptionBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const decoded = decodeHtmlEntities(text);
  const isLong = decoded.length > 200;
  const displayText = isLong && !expanded ? decoded.slice(0, 200) + '...' : decoded;

  return (
    <div className="bg-white rounded-xl border border-[#EBEBEB] p-4 md:p-5 mb-4">
      <p className="text-[14px] text-[#646464] leading-relaxed whitespace-pre-wrap">{displayText}</p>
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-xs text-[#0066FF] hover:underline"
        >
          {expanded ? '收起' : '展开全文'}
        </button>
      )}
    </div>
  );
}

export default function DebateDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [debate, setDebate] = useState<Debate | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'roundtable' | 'bets' | 'ruling'>('roundtable');
  const [running, setRunning] = useState(false);
  const [showPoster, setShowPoster] = useState(false);
  const { wallet, buyShares: walletBuyShares, refresh: refreshWallet } = useWallet();

  const handleBuyShares = async (optionKey: string, quantity: number) => {
    try {
      // 买入 = 同时派出分身参战
      const userId = localStorage.getItem('arena_user_id') || crypto.randomUUID();
      localStorage.setItem('arena_user_id', userId);
      const personality = localStorage.getItem('arena_personality') || '';
      const labels: Record<string, string> = {
        rational: '理性分析，数据说话',
        idealist: '关心公平正义，理想主义',
        pragmatist: '务实派，看重可操作性',
        skeptic: '质疑派，对主流保持警惕',
      };

      // 1. 派分身加入辩论（忽略已加入错误）
      await fetch(`/api/debates/${id}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          user_name: '我的分身',
          personality_override: labels[personality] || '理性思考，独立判断',
        }),
      }).catch(() => {});

      // 2. 买入观点股
      await walletBuyShares(id, optionKey, quantity);

      // 3. 刷新辩论数据
      const res = await fetch(`/api/debates/${id}`);
      if (res.ok) setDebate(await res.json());
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : '买入失败');
    }
  };

  useEffect(() => {
    fetch(`/api/debates/${id}`)
      .then((r) => r.json())
      .then((d) => { setDebate(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F6F6F6]">
        <div className="text-[#8590A6] text-sm">加载中...</div>
      </div>
    );
  }

  if (!debate) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#F6F6F6] gap-4">
        <div className="text-[#8590A6]">辩论不存在</div>
        <Link href="/" className="text-[#0066FF] text-sm hover:underline">返回首页</Link>
      </div>
    );
  }

  const isFinished = debate.status === 'finished';
  const hasBets = debate.bets.length > 0;
  const hasTranscript = debate.transcript.length > 0;

  // Group transcript by phase
  const phases = debate.transcript.reduce<Record<string, Message[]>>((acc, msg) => {
    const key = msg.phase || 'unknown';
    if (!acc[key]) acc[key] = [];
    acc[key].push(msg);
    return acc;
  }, {});

  const handleRun = async () => {
    setRunning(true);
    try {
      const res = await fetch(`/api/debates/${id}/run`, { method: 'POST' });
      if (res.ok) {
        window.location.reload();
      } else {
        const err = await res.json();
        alert(err.error || '运行失败');
      }
    } catch {
      alert('网络错误');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F6F6F6]">
      {/* Header */}
      <header className="bg-white border-b border-[#EBEBEB] sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 md:px-6 h-14 flex items-center gap-4">
          <Link href="/" className="text-[#8590A6] hover:text-[#1A1A1A] transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="text-base font-semibold text-[#1A1A1A] truncate">{debate.title}</h1>
          </div>
          {isFinished ? (
            <span className="shrink-0 flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full bg-[#E8F5E9] text-[#2E7D32]">
              ✓ 已结算
            </span>
          ) : debate.status === 'running' ? (
            <span className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full bg-[#FFF3E0] text-[#E65100]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#E65100] animate-pulse" />
              交易中
            </span>
          ) : (
            <span className="shrink-0 px-2.5 py-1 text-xs rounded-full bg-[#E8F0FE] text-[#0066FF] font-medium">
              可买入
            </span>
          )}
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-5xl mx-auto px-4 md:px-6 py-4 md:py-6 flex flex-col lg:flex-row gap-4 md:gap-6">
        {/* Left: Transcript + Ruling */}
        <div className="flex-1 min-w-0">
          {/* Market status bar */}
          <div className="bg-white rounded-xl border border-[#EBEBEB] p-3 mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                isFinished ? 'bg-[#E8F5E9] text-[#2E7D32]' : 'bg-[#FFF3E0] text-[#E65100]'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${isFinished ? 'bg-[#2E7D32]' : 'bg-[#E65100] animate-pulse'}`} />
                {isFinished ? '已结算' : '交易进行中'}
              </div>
              {debate.bets.length > 0 && (
                <span className="text-xs text-[#8590A6]">
                  {debate.bets.length} 位交易员 · 总池 {debate.bets.reduce((s, b) => s + b.amount, 0)} 积分
                </span>
              )}
            </div>
            {isFinished && debate.result && (
              <span className="text-xs font-semibold text-[#00C853]">胜出观点：{debate.result}</span>
            )}
          </div>

          {/* Description */}
          {debate.description && (
            <DescriptionBlock text={debate.description} />
          )}

          {/* Tab navigation */}
          {(hasTranscript || hasBets) && (
            <div className="flex items-center gap-1 mb-4 bg-white rounded-xl border border-[#EBEBEB] p-1.5 overflow-x-auto">
              {[
                { key: 'roundtable' as const, label: '圆桌讨论', count: debate.transcript.length, show: hasTranscript },
                { key: 'bets' as const, label: '下注详情', count: debate.bets.length, show: hasBets },
                { key: 'ruling' as const, label: '裁决报告', count: 0, show: isFinished },
              ].filter(t => t.show).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-4 py-2 text-sm rounded-lg transition-all whitespace-nowrap ${
                    activeTab === tab.key
                      ? 'bg-[#0066FF] text-white font-medium shadow-sm'
                      : 'text-[#8590A6] hover:bg-[#F5F5F5] hover:text-[#1A1A1A]'
                  }`}
                >
                  {tab.label}
                  {tab.count > 0 && <span className="ml-1 opacity-60">{tab.count}</span>}
                </button>
              ))}
            </div>
          )}

          {/* Roundtable transcript - Zhihu comment style */}
          {activeTab === 'roundtable' && hasTranscript && (
            <div className="bg-white rounded-xl border border-[#EBEBEB] overflow-hidden">
              {Object.entries(phases).map(([phase, messages]) => (
                <div key={phase}>
                  <div className="sticky top-14 z-10 px-4 md:px-5 py-2.5 bg-[#FAFAFA] border-b border-[#EBEBEB]">
                    <span className="text-xs font-semibold text-[#8590A6] uppercase tracking-wider">{phase}</span>
                    <span className="ml-2 text-xs text-[#C8C8C8]">{messages.length} 条发言</span>
                  </div>
                  {messages.map((msg, i) => (
                    <RoundtableComment
                      key={`${phase}-${i}`}
                      agent={msg.agent}
                      content={msg.content}
                      phase={phase}
                      targetAgent={msg.target_agent}
                      defected={msg.defected}
                      oldLabel={msg.old_label}
                      newLabel={msg.new_label}
                    />
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* Bet details */}
          {activeTab === 'bets' && hasBets && (
            <div className="bg-white rounded-xl border border-[#EBEBEB] p-4 md:p-5">
              <h4 className="text-xs font-semibold text-[#8590A6] uppercase tracking-wider mb-3">Agent 下注详情</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {debate.bets.map((bet) => {
                  const agent = getAgent(bet.agentName);
                  const payout = debate.judgment?.payouts?.[bet.agentName.replace(/^[^\u4e00-\u9fff]+/, '')];
                  const isWin = bet.won === true;

                  return (
                    <div
                      key={bet.id}
                      className={`flex items-start gap-3 p-3 rounded-xl border ${
                        isWin ? 'border-[#C8E6C9] bg-[#F1FFF6]'
                        : bet.won === false ? 'border-[#FFCDD2] bg-[#FFF5F5]'
                        : 'border-[#EBEBEB] bg-white'
                      }`}
                    >
                      <div className="w-9 h-9 rounded-full flex items-center justify-center text-lg shrink-0" style={{ backgroundColor: agent.bg }}>
                        {agent.emoji}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium" style={{ color: agent.color }}>{bet.agentName.replace(/^[^\u4e00-\u9fff]+/, '')}</span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs text-[#8590A6] tabular-nums">{bet.amount}分</span>
                            {payout && (
                              <span className={`text-xs font-bold tabular-nums ${isWin ? 'text-[#00C853]' : 'text-[#F44336]'}`}>
                                {isWin ? '+' : ''}{payout.net}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs px-1.5 py-0.5 rounded bg-[#F0F0F0] text-[#666]">{bet.option}</span>
                          <span className="text-xs text-[#8590A6]">信心 {Math.round(bet.confidence * 100)}%</span>
                        </div>
                        {bet.reasoning && <p className="text-xs text-[#999] mt-1 line-clamp-2">{bet.reasoning}</p>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Ruling */}
          {activeTab === 'ruling' && debate.judgment && (
            <div className="bg-white rounded-xl border border-[#EBEBEB] p-4 md:p-5 space-y-4">
              {/* Judge header */}
              <div className="flex items-start gap-3">
                <img src="/liu-kanshan.png" alt="刘看山" className="w-11 h-11 rounded-full shrink-0 border-2 border-[#0084FF]/20" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-base font-bold text-[#37474F]">刘看山</span>
                    <span className="text-xs bg-[#0084FF] text-white px-1.5 py-0.5 rounded">裁判</span>
                    {debate.judgment.mvp && (
                      <span className="text-xs bg-[#FF6D00] text-white px-1.5 py-0.5 rounded">MVP: {debate.judgment.mvp}</span>
                    )}
                  </div>
                  {debate.judgment.mvp_reason && (
                    <p className="text-xs text-[#FF6D00] mb-2 italic">{debate.judgment.mvp_reason}</p>
                  )}
                  <div className="text-[15px] text-[#333] leading-relaxed whitespace-pre-wrap bg-[#F9FAFB] border-l-[3px] border-[#0066FF] pl-4 py-3 rounded-r-lg">
                    {debate.judgment.reasoning}
                  </div>
                </div>
              </div>

              {/* Option analysis */}
              {debate.judgment.option_analysis && Object.keys(debate.judgment.option_analysis).length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-[#8590A6] mb-2">各选项分析</h5>
                  <div className="space-y-2">
                    {Object.entries(debate.judgment.option_analysis).map(([optKey, analysis]) => {
                      const optLabel = debate.options[parseInt(optKey.replace('option_', ''), 10)] || optKey;
                      const isWin = debate.result === optLabel;
                      return (
                        <div key={optKey} className={`p-3 rounded-xl border ${isWin ? 'border-[#C8E6C9] bg-[#F1FFF6]' : 'border-[#EBEBEB] bg-[#FAFAFA]'}`}>
                          <div className="flex items-center justify-between mb-1">
                            <span className={`text-sm font-medium ${isWin ? 'text-[#2E7D32]' : 'text-[#333]'}`}>{isWin && '✓ '}{optLabel}</span>
                            <span className={`text-sm font-bold tabular-nums ${isWin ? 'text-[#2E7D32]' : 'text-[#666]'}`}>{analysis.score}分</span>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                            <div><span className="text-[#2E7D32]">优势：</span><span className="text-[#666]">{analysis.strength}</span></div>
                            <div><span className="text-[#C62828]">弱点：</span><span className="text-[#666]">{analysis.weakness}</span></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Highlights */}
              {debate.judgment.highlights?.length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-[#8590A6] mb-2">精彩瞬间</h5>
                  {debate.judgment.highlights.map((h, i) => (
                    <p key={i} className="text-xs text-[#666] flex items-start gap-1.5 mb-1">
                      <span className="text-[#FF6D00] mt-0.5">★</span>{h}
                    </p>
                  ))}
                </div>
              )}

              {/* Score bars */}
              {debate.judgment.scores && Object.keys(debate.judgment.scores).length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-[#8590A6] mb-2">评分明细</h5>
                  {Object.entries(debate.judgment.scores).map(([optKey, scores]) => {
                    const total = scores.total ?? 0;
                    const optLabel = debate.options[parseInt(optKey.replace('option_', ''), 10)] || optKey;
                    const isWin = debate.result === optLabel;
                    return (
                      <div key={optKey} className="flex items-center gap-2 mb-1.5">
                        <span className={`text-xs min-w-[80px] truncate ${isWin ? 'font-bold text-[#00C853]' : 'text-[#666]'}`}>{optLabel}</span>
                        <div className="flex-1 h-4 bg-[#F0F0F0] rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.min(total, 100)}%`, backgroundColor: isWin ? '#00C853' : '#0066FF', opacity: isWin ? 1 : 0.6 }} />
                        </div>
                        <span className={`text-xs tabular-nums min-w-[28px] text-right ${isWin ? 'font-bold text-[#00C853]' : 'text-[#999]'}`}>{total}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Data sources */}
              {(debate.judgment.data_sources ?? []).length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-[#8590A6] mb-1">数据裁定依据</h5>
                  {(debate.judgment.data_sources ?? []).map((src, i) => (
                    <div key={i} className="text-[12px] px-3 py-1.5 rounded-lg bg-[#E8F0FE] text-[#0066FF] border border-[#D0E0FE] mb-1">
                      📊 {src}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!hasTranscript && !hasBets && (
            <div className="bg-white rounded-xl border border-[#EBEBEB] p-12 text-center">
              <div className="text-4xl mb-3">⚔️</div>
              <p className="text-[#8590A6] text-sm">辩论尚未开始</p>
              <p className="text-[#C8C8C8] text-xs mt-1">在右侧买入你支持的观点，系统将自动开启辩论</p>
            </div>
          )}
        </div>

        {/* Right sidebar: Betting panel */}
        <div className="lg:w-80 shrink-0">
          <div className="lg:sticky lg:top-20">
            <BettingPanel debate={debate} wallet={wallet} onBuyShares={handleBuyShares} />

            {/* Winner payout card */}
            {isFinished && debate.judgment && (
              <>
                <div className="mt-4 bg-gradient-to-br from-[#F1FFF6] to-[#E8F5E9] rounded-xl border border-[#C8E6C9] p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <img src="/liu-kanshan.png" alt="刘看山" className="w-5 h-5 rounded-full" />
                    <span className="text-sm font-bold text-[#2E7D32]">裁定：{debate.result}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {debate.bets.map((bet) => {
                      const payout = debate.judgment?.payouts?.[bet.agentName.replace(/^[^\u4e00-\u9fff]+/, '')];
                      const agent = getAgent(bet.agentName);
                      const isWin = bet.won === true;
                      const profit = payout?.net ?? 0;
                      return (
                        <div key={bet.id} className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${isWin ? 'bg-[#E8F5E9] text-[#2E7D32]' : 'bg-[#FFEBEE] text-[#C62828]'}`}>
                          <span>{agent.emoji}</span>
                          <span className="font-medium tabular-nums">{isWin ? '+' : ''}{profit}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Share poster button */}
                <button
                  onClick={() => setShowPoster(true)}
                  className="mt-3 w-full py-2.5 bg-[#07C160] text-white text-sm font-medium rounded-xl hover:bg-[#06AD56] transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                >
                  📤 生成结算海报
                </button>

                {/* 观点出圈 notification */}
                {(debate as unknown as Record<string, unknown>).zhihu_post && (
                  <div className="mt-3 bg-gradient-to-r from-[#E8F0FE] to-[#F0F4FF] rounded-xl border border-[#D0E0FE] p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">🌊</span>
                      <span className="text-sm font-bold text-[#0066FF]">观点已出圈</span>
                    </div>
                    <p className="text-xs text-[#646464] leading-relaxed">
                      获胜论点已自动发布到知乎圈子，真实知乎用户正在看到、讨论这个观点
                    </p>
                    <div className="mt-2 text-[10px] text-[#8590A6]">
                      你的 AI 分身正在替你影响真实世界的舆论
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Victory poster modal */}
      {showPoster && debate.judgment && (
        <VictoryPoster debate={debate} onClose={() => setShowPoster(false)} />
      )}
    </div>
  );
}
