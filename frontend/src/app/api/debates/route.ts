import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Transform a backend debate object into the format the frontend expects.
 */
function transformDebate(d: Record<string, unknown>): Record<string, unknown> {
  const options = (d.options as Array<{ key: string; label: string }>) || [];
  const bets = (d.bets as Array<Record<string, unknown>>) || [];
  const judgment = d.judgment as Record<string, unknown> | null;
  const payouts = (judgment?.payouts as Record<string, Record<string, unknown>>) || {};

  // List endpoint sends transcript_count instead of full transcript
  const transcript = (d.transcript as Array<Record<string, unknown>>) || [];
  const transcriptCount = (d.transcript_count as number) ?? transcript.length;

  // Map status
  const rawStatus = d.status as string;
  let status = rawStatus;
  if (rawStatus === 'completed') status = 'finished';
  if (rawStatus === 'running' && judgment) status = 'finished';

  return {
    id: d.id,
    title: d.title,
    description: (d.context as string) || '',
    options: options.map((o) => o.label),
    option_prices: (d.market_prices as Record<string, number>) || {},
    status,
    phase: d.phase || '',
    result: judgment ? (judgment.winning_label as string) : null,
    // List view: build minimal transcript array with correct length
    transcript: transcript.length > 0
      ? transcript.map((msg) => ({
          agent: `${msg.agent_emoji || ''}${msg.agent_name || ''}`,
          content: msg.content,
          phase: msg.phase,
        }))
      : Array.from({ length: transcriptCount }, () => ({ agent: '', content: '', phase: '' })),
    bets: bets.map((b, i) => {
      const name = b.agent_name as string;
      const payout = payouts[name] as Record<string, unknown> | undefined;
      return {
        id: `bet-${i}`,
        agentName: `${b.agent_emoji || ''}${name}`,
        option: b.chosen_label,
        amount: b.bet_amount,
        confidence: b.confidence,
        reasoning: b.reasoning || null,
        won: payout ? payout.result === 'win' : null,
      };
    }),
    judgment: judgment
      ? {
          mvp: judgment.mvp,
          winning_label: judgment.winning_label,
          payouts,
        }
      : null,
    createdAt: d.created_at,
  };
}

export async function GET() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000); // 15s timeout
    const response = await fetch(`${BACKEND_URL}/api/debates`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!response.ok) {
      return NextResponse.json({ debates: [] });
    }
    const data = await response.json();
    const debates = (data.debates || []).map(transformDebate);
    return NextResponse.json({ debates });
  } catch (error) {
    console.error('Backend connection error:', error);
    return NextResponse.json({ debates: [] });
  }
}

export async function POST(request: Request) {
  const body = await request.json();
  const { title, description, options } = body;

  if (!title || !options || options.length < 2) {
    return NextResponse.json(
      { error: '需要标题和至少两个选项' },
      { status: 400 }
    );
  }

  // Transform string[] options to backend format [{key, label}]
  const backendOptions = (options as string[]).map((label: string, i: number) => ({
    key: `option_${i}`,
    label,
  }));

  try {
    const response = await fetch(`${BACKEND_URL}/api/debates`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        context: description || '',
        options: backendOptions,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: `后端创建失败: ${error}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json({ debate: transformDebate(result) });
  } catch (error) {
    console.error('Backend connection error:', error);
    return NextResponse.json(
      { error: '无法连接到后端服务，请确保 Python 后端正在运行' },
      { status: 502 }
    );
  }
}
