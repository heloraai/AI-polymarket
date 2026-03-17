import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const res = await fetch(`${BACKEND_URL}/api/debates/${id}`, {
      cache: 'no-store',
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: 'Debate not found' },
        { status: res.status }
      );
    }

    const raw = await res.json();

    const options = (raw.options || []) as Array<{ key: string; label: string }>;
    const bets = (raw.bets || []) as Array<Record<string, unknown>>;
    const transcript = (raw.transcript || []) as Array<Record<string, unknown>>;
    const judgment = (raw.judgment as Record<string, unknown>) || null;
    const payouts = (judgment?.payouts as Record<string, Record<string, unknown>>) || {};

    const rawStatus = raw.status as string;
    const status = rawStatus === 'completed' ? 'finished' : rawStatus;

    const debate = {
      id: raw.id,
      title: raw.title,
      description: (raw.context as string) || '',
      options: options.map((o) => o.label),
      option_prices: raw.market_prices || {},
      status,
      phase: raw.phase || '',
      result: judgment ? (judgment.winning_label as string) : null,
      transcript: transcript.map((msg) => ({
        agent: `${msg.agent_emoji || ''}${msg.agent_name || ''}`,
        content: msg.content,
        phase: msg.phase,
        target_agent: msg.target_agent || undefined,
        defected: msg.defected || false,
        old_label: msg.old_label || undefined,
        new_label: msg.new_label || undefined,
      })),
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
            reasoning: judgment.reasoning,
            option_analysis: judgment.option_analysis || {},
            scores: judgment.scores,
            mvp: judgment.mvp,
            mvp_reason: judgment.mvp_reason || '',
            highlights: judgment.highlights,
            data_sources: judgment.data_sources || [],
            total_pool: judgment.total_pool,
            loser_pool: judgment.loser_pool,
            payouts,
          }
        : null,
      zhihu_post: raw.zhihu_post || null,
      createdAt: raw.created_at,
    };

    return NextResponse.json(debate);
  } catch (error) {
    console.error('Failed to fetch debate:', error);
    return NextResponse.json(
      { error: 'Failed to fetch debate' },
      { status: 500 }
    );
  }
}
