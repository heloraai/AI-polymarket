import { NextRequest, NextResponse } from 'next/server';
import { exchangeCodeForToken, getUserInfo, getSoftMemory } from '@/lib/auth';

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code');

  if (!code) {
    return NextResponse.redirect(new URL('/?error=no_code', request.url));
  }

  try {
    const tokenData = await exchangeCodeForToken(code);
    const { accessToken } = tokenData;

    const [userInfo, softMemory] = await Promise.all([
      getUserInfo(accessToken),
      getSoftMemory(accessToken),
    ]);

    // Build personality from soft memory fragments
    const personality = softMemory.length > 0
      ? softMemory.slice(0, 10).join('\n')
      : '';

    const userId = userInfo.route || userInfo.email || userInfo.name || 'unknown';

    const response = NextResponse.redirect(new URL('/', request.url));

    // Store user info in cookies (no database needed)
    response.cookies.set('userId', userId, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 30,
    });
    response.cookies.set('userName', encodeURIComponent(userInfo.name || ''), {
      httpOnly: false,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 30,
    });
    response.cookies.set('userAvatar', encodeURIComponent(userInfo.avatarUrl || ''), {
      httpOnly: false,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 30,
    });
    response.cookies.set('accessToken', accessToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 30,
    });
    if (personality) {
      response.cookies.set('userPersonality', encodeURIComponent(personality), {
        httpOnly: false,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 60 * 60 * 24 * 30,
      });
    }

    return response;
  } catch (error) {
    console.error('OAuth callback error:', error);
    return NextResponse.redirect(new URL('/?error=auth_failed', request.url));
  }
}
