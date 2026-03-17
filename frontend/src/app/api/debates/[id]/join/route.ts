import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const body = await request.json();

    const res = await fetch(`${BACKEND_URL}/api/debates/${id}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Join failed' }));
      return NextResponse.json(
        { error: error.detail || 'Join failed' },
        { status: res.status }
      );
    }

    const result = await res.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('Join debate error:', error);
    return NextResponse.json(
      { error: 'Failed to join debate' },
      { status: 500 }
    );
  }
}
