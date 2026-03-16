import { cookies } from 'next/headers';

const API_BASE_URL = process.env.SECONDME_API_BASE_URL!;
const CLIENT_ID = process.env.SECONDME_CLIENT_ID!;
const CLIENT_SECRET = process.env.SECONDME_CLIENT_SECRET!;
const REDIRECT_URI = process.env.SECONDME_REDIRECT_URI!;
const OAUTH_URL = process.env.SECONDME_OAUTH_URL!;

export function getAuthUrl(): string {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: 'code',
    state: crypto.randomUUID(),
  });
  return `${OAUTH_URL}?${params.toString()}`;
}

export async function exchangeCodeForToken(code: string) {
  const response = await fetch(`${API_BASE_URL}/api/oauth/token/code`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: REDIRECT_URI,
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
    }),
  });

  const result = await response.json();
  if (result.code !== 0 || !result.data) {
    throw new Error(`Token exchange failed: ${result.message || 'Unknown error'}`);
  }

  return result.data;
}

export async function refreshAccessToken(refreshToken: string) {
  const response = await fetch(`${API_BASE_URL}/api/oauth/token/refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
    }),
  });

  const result = await response.json();
  if (result.code !== 0 || !result.data) {
    throw new Error(`Token refresh failed: ${result.message || 'Unknown error'}`);
  }

  return result.data;
}

export async function getUserInfo(accessToken: string) {
  const response = await fetch(`${API_BASE_URL}/api/secondme/user/info`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const result = await response.json();
  if (result.code !== 0 || !result.data) {
    throw new Error(`Get user info failed: ${result.message || 'Unknown error'}`);
  }

  return result.data;
}

export async function getSoftMemory(accessToken: string): Promise<string[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/secondme/user/softmemory`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    const result = await response.json();
    if (result.code !== 0 || !result.data) {
      return [];
    }

    // result.data.list is an array of memory fragments
    const list = result.data.list || [];
    return list.map((item: { content?: string; text?: string }) =>
      item.content || item.text || ''
    ).filter(Boolean);
  } catch {
    return [];
  }
}

export async function getSessionUserId(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get('userId')?.value ?? null;
}
