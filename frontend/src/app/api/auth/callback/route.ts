import { NextRequest, NextResponse } from 'next/server';
import { exchangeCodeForToken, getUserInfo, getSoftMemory } from '@/lib/auth';
import { prisma } from '@/lib/db';

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code');

  if (!code) {
    return NextResponse.redirect(new URL('/?error=no_code', request.url));
  }

  try {
    const tokenData = await exchangeCodeForToken(code);
    const { accessToken, refreshToken, expiresIn } = tokenData;

    const [userInfo, softMemory] = await Promise.all([
      getUserInfo(accessToken),
      getSoftMemory(accessToken),
    ]);

    const tokenExpiresAt = new Date(Date.now() + expiresIn * 1000);

    // Build personality from soft memory fragments
    const personality = softMemory.length > 0
      ? softMemory.slice(0, 10).join('\n')  // Take up to 10 memory fragments
      : '';

    const user = await prisma.user.upsert({
      where: { secondmeUserId: userInfo.route || userInfo.email || userInfo.name },
      create: {
        secondmeUserId: userInfo.route || userInfo.email || userInfo.name,
        name: userInfo.name,
        avatarUrl: userInfo.avatarUrl,
        accessToken,
        refreshToken,
        tokenExpiresAt,
      },
      update: {
        name: userInfo.name,
        avatarUrl: userInfo.avatarUrl,
        accessToken,
        refreshToken,
        tokenExpiresAt,
      },
    });

    const response = NextResponse.redirect(new URL('/', request.url));

    // Store personality in cookie for the frontend to pass to backend
    if (personality) {
      response.cookies.set('userPersonality', encodeURIComponent(personality), {
        httpOnly: false,  // Readable by frontend JS
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 60 * 60 * 24 * 30,
      });
    }
    response.cookies.set('userId', user.id, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 30, // 30 days
    });

    return response;
  } catch (error) {
    console.error('OAuth callback error:', error);
    return NextResponse.redirect(new URL('/?error=auth_failed', request.url));
  }
}
