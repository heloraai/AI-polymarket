import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ userId: string }> }
) {
  const { userId } = await params;
  try {
    const res = await fetch(`${BACKEND_URL}/api/wallet/${userId}`, { cache: 'no-store' });
    if (!res.ok) return NextResponse.json({ error: 'Wallet not found' }, { status: res.status });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: 'Failed to fetch wallet' }, { status: 500 });
  }
}
