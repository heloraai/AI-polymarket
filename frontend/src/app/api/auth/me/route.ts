import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET() {
  const cookieStore = await cookies();
  const userId = cookieStore.get('userId')?.value;

  if (!userId) {
    return NextResponse.json({ user: null });
  }

  const name = decodeURIComponent(cookieStore.get('userName')?.value || '');
  const avatarUrl = decodeURIComponent(cookieStore.get('userAvatar')?.value || '') || null;

  return NextResponse.json({
    user: {
      id: userId,
      name: name || userId,
      avatarUrl,
    },
  });
}
