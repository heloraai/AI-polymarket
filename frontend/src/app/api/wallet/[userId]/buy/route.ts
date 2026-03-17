import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ userId: string }> }
) {
  const { userId } = await params;
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/api/wallet/${userId}/buy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Buy failed' }));
      return NextResponse.json({ error: err.detail || 'Buy failed' }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: 'Failed to buy shares' }, { status: 500 });
  }
}
