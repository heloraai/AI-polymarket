import { NextResponse } from 'next/server';
import { getSessionUserId } from '@/lib/auth';
import { prisma } from '@/lib/db';

export async function GET() {
  const userId = await getSessionUserId();

  if (!userId) {
    return NextResponse.json({ user: null });
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      name: true,
      avatarUrl: true,
      secondmeUserId: true,
    },
  });

  return NextResponse.json({ user });
}
