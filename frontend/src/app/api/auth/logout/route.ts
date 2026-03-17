import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const response = NextResponse.redirect(new URL('/', request.url));
  response.cookies.delete('userId');
  response.cookies.delete('userName');
  response.cookies.delete('userAvatar');
  response.cookies.delete('accessToken');
  response.cookies.delete('userPersonality');
  return response;
}
