'use client';

import { useState, useEffect, useCallback } from 'react';

const PERSONALITY_OPTIONS = [
  {
    id: 'rational',
    emoji: '🧠',
    label: '理性派',
    tagline: '数据说话，逻辑至上',
    description: '你相信证据和推理，不轻易被情绪左右。面对争论，你习惯先看数据再下结论。',
    color: '#0066FF',
    bgGradient: 'from-blue-500/10 to-blue-600/5',
    glowColor: 'shadow-blue-500/20',
  },
  {
    id: 'idealist',
    emoji: '🔥',
    label: '理想派',
    tagline: '世界应该更好',
    description: '你关心公平正义，相信改变的力量。即使知道现实骨感，你仍然为理想发声。',
    color: '#F1403C',
    bgGradient: 'from-red-500/10 to-orange-500/5',
    glowColor: 'shadow-red-500/20',
  },
  {
    id: 'pragmatist',
    emoji: '⚡',
    label: '务实派',
    tagline: '能落地的才是好方案',
    description: '你看重可操作性和投入产出比。华丽的理论不如一个管用的方案。',
    color: '#00C853',
    bgGradient: 'from-green-500/10 to-emerald-500/5',
    glowColor: 'shadow-green-500/20',
  },
  {
    id: 'skeptic',
    emoji: '🦊',
    label: '质疑派',
    tagline: '大家都说对的，未必对',
    description: '你天然对主流观点保持警惕。别人越笃定，你越想找漏洞。',
    color: '#9C27B0',
    bgGradient: 'from-purple-500/10 to-violet-500/5',
    glowColor: 'shadow-purple-500/20',
  },
];

interface OnboardingProps {
  onComplete: (personality: string) => void;
}

export default function Onboarding({ onComplete }: OnboardingProps) {
  const [step, setStep] = useState(0); // 0: splash, 1: typing, 2: pick personality
  const [showContent, setShowContent] = useState(false);
  const [typedLines, setTypedLines] = useState<number[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [cardsVisible, setCardsVisible] = useState(false);
  const [exiting, setExiting] = useState(false);
  const [loggingIn, setLoggingIn] = useState(false);

  useEffect(() => {
    if (step === 0) {
      const t = setTimeout(() => setShowContent(true), 300);
      return () => clearTimeout(t);
    }
  }, [step]);

  const introLines = [
    '如果观点有价格，你的观点值多少？',
    '',
    '知乎热榜上每天几百万人争论不休，',
    '但从来没人敢为自己说的话下注。',
    '',
    '我们建了一个交易所。',
    '每个观点都有价格，每次开口都是交易。',
    '说对了，赚走对手的积分。说错了，血本无归。',
    '',
    '欢迎来到观点交易所。',
  ];

  useEffect(() => {
    if (step === 1) {
      let i = 0;
      const interval = setInterval(() => {
        if (i < introLines.length) {
          setTypedLines(prev => [...prev, i]);
          i++;
        } else {
          clearInterval(interval);
          setTimeout(() => setStep(2), 800);
        }
      }, 400);
      return () => clearInterval(interval);
    }
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (step === 2) {
      const t = setTimeout(() => setCardsVisible(true), 200);
      return () => clearTimeout(t);
    }
  }, [step]);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleLogin = useCallback(() => {
    setLoggingIn(true);
    // Redirect to SecondMe OAuth
    window.location.href = '/api/auth/login';
  }, []);

  const handleConfirm = useCallback(() => {
    if (!selectedId) return;
    const selected = PERSONALITY_OPTIONS.find(p => p.id === selectedId);
    if (!selected) return;

    setExiting(true);

    // Generate user ID and save
    const userId = crypto.randomUUID();
    localStorage.setItem('arena_user_id', userId);
    localStorage.setItem('arena_personality', selectedId);
    localStorage.setItem('arena_onboarded', 'true');

    // Init wallet
    fetch(`/api/wallet/${userId}`).catch(() => {});

    setTimeout(() => {
      onComplete(selected.description);
    }, 600);
  }, [selectedId, onComplete]);

  // Step 0: Splash with SecondMe login
  if (step === 0) {
    return (
      <div className="fixed inset-0 z-[100] bg-[#0a0a0a] flex items-center justify-center overflow-hidden">
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }} />

        <div className="absolute w-[500px] h-[500px] rounded-full bg-blue-600/10 blur-[120px] animate-float-slow top-[-100px] right-[-100px]" />
        <div className="absolute w-[400px] h-[400px] rounded-full bg-red-600/8 blur-[100px] animate-float-slow-reverse bottom-[-50px] left-[-50px]" />

        <div className={`text-center transition-all duration-1000 ${showContent ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <div className="mb-8 flex items-center justify-center">
            <div className="relative">
              <img src="/liu-kanshan.png" alt="刘看山" className="w-20 h-20 rounded-full border-2 border-white/20 shadow-lg" />
              <div className="absolute -inset-4 rounded-full bg-blue-500/10 blur-xl animate-pulse-slow" />
            </div>
          </div>

          <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight mb-4">
            观点交易所
          </h1>
          <p className="text-lg text-gray-400 mb-2 tracking-wide">
            知乎热榜出题 · AI 辩论下注 · 刘看山裁定
          </p>
          <p className="text-sm text-gray-600 mb-12">
            A2A for Reconnect Hackathon &nbsp;|&nbsp; 知乎 × Second Me
          </p>

          {/* SecondMe 登录按钮 — 主要 CTA */}
          <button
            onClick={handleLogin}
            disabled={loggingIn}
            className="group relative px-10 py-4 bg-white text-[#0a0a0a] font-semibold text-lg rounded-full overflow-hidden transition-all duration-300 hover:shadow-[0_0_40px_rgba(255,255,255,0.15)] hover:scale-105 active:scale-95 mb-4 disabled:opacity-50"
          >
            <span className="relative z-10 flex items-center gap-2">
              {loggingIn ? (
                <>
                  <span className="w-4 h-4 border-2 border-gray-400 border-t-gray-800 rounded-full animate-spin" />
                  连接中...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0" />
                  </svg>
                  用 Second Me 登录
                </>
              )}
            </span>
            <div className="absolute inset-0 bg-gradient-to-r from-blue-400 to-purple-400 opacity-0 group-hover:opacity-10 transition-opacity" />
          </button>

          <p className="text-gray-700 text-xs mt-6">
            登录后你的 AI 分身将自动获得 200 积分入场
          </p>
        </div>
      </div>
    );
  }

  // Step 1: Typewriter story
  if (step === 1) {
    return (
      <div className="fixed inset-0 z-[100] bg-[#0a0a0a] flex items-center justify-center overflow-hidden">
        <div className="absolute w-[500px] h-[500px] rounded-full bg-blue-600/10 blur-[120px] animate-float-slow top-[-100px] right-[-100px]" />

        <div className="max-w-lg px-8">
          {introLines.map((line, i) => (
            <div
              key={i}
              className={`transition-all duration-500 ${
                typedLines.includes(i)
                  ? 'opacity-100 translate-y-0'
                  : 'opacity-0 translate-y-4'
              }`}
            >
              {line === '' ? (
                <div className="h-6" />
              ) : i === introLines.length - 1 ? (
                <p className="text-xl text-white font-medium mb-2 leading-relaxed">{line}</p>
              ) : (
                <p className="text-lg text-gray-400 mb-2 leading-relaxed">{line}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Step 2: Personality picker
  return (
    <div className={`fixed inset-0 z-[100] bg-[#0a0a0a] flex flex-col items-center justify-center overflow-hidden transition-opacity duration-500 ${exiting ? 'opacity-0 scale-105' : 'opacity-100'}`}>
      <div className="absolute w-[600px] h-[600px] rounded-full bg-blue-600/5 blur-[150px] top-[-200px] left-1/2 -translate-x-1/2" />

      <div className={`mb-10 text-center transition-all duration-700 ${cardsVisible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'}`}>
        <h2 className="text-3xl font-bold text-white mb-3">选择你的交易风格</h2>
        <p className="text-gray-500 text-sm">这将决定你的 AI 分身在交易所中如何思考和下注</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl px-6 mb-10">
        {PERSONALITY_OPTIONS.map((p, idx) => {
          const isSelected = selectedId === p.id;
          return (
            <button
              key={p.id}
              onClick={() => handleSelect(p.id)}
              className={`relative text-left p-6 rounded-2xl border transition-all duration-500 cursor-pointer group
                ${cardsVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}
                ${isSelected
                  ? `border-white/30 bg-gradient-to-br ${p.bgGradient} shadow-lg ${p.glowColor} scale-[1.02]`
                  : 'border-white/[0.06] bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04]'
                }
              `}
              style={{ transitionDelay: `${idx * 100 + 200}ms` }}
            >
              {isSelected && (
                <div className="absolute top-3 right-3 w-6 h-6 rounded-full bg-white flex items-center justify-center animate-scale-in">
                  <svg className="w-4 h-4 text-[#0a0a0a]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}

              <div className="text-4xl mb-3 transition-transform duration-300 group-hover:scale-110">{p.emoji}</div>
              <h3 className={`text-lg font-bold mb-1 transition-colors ${isSelected ? 'text-white' : 'text-gray-300'}`}>
                {p.label}
              </h3>
              <p className="text-xs font-medium mb-2" style={{ color: isSelected ? p.color : '#666' }}>
                {p.tagline}
              </p>
              <p className={`text-sm leading-relaxed ${isSelected ? 'text-gray-300' : 'text-gray-600'}`}>
                {p.description}
              </p>
            </button>
          );
        })}
      </div>

      <div className={`transition-all duration-500 ${selectedId ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'}`}>
        <button
          onClick={handleConfirm}
          className="group relative px-12 py-4 bg-white text-[#0a0a0a] font-semibold text-lg rounded-full overflow-hidden transition-all duration-300 hover:shadow-[0_0_40px_rgba(255,255,255,0.15)] hover:scale-105 active:scale-95"
        >
          <span className="relative z-10">
            以「{PERSONALITY_OPTIONS.find(p => p.id === selectedId)?.label}」身份入场
          </span>
          <div className="absolute inset-0 bg-gradient-to-r from-blue-400 to-purple-400 opacity-0 group-hover:opacity-10 transition-opacity" />
        </button>
      </div>
    </div>
  );
}
