import { NextResponse } from 'next/server';
import { getAuthUrl } from '@/lib/auth';

export async function GET() {
  const authUrl = getAuthUrl();
  return NextResponse.redirect(authUrl);
}
