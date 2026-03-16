'use client';

interface LoginButtonProps {
  user: { name: string; avatarUrl: string | null } | null;
}

export default function LoginButton({ user }: LoginButtonProps) {
  if (user) {
    return (
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-[#0066FF] flex items-center justify-center text-white text-sm font-medium overflow-hidden">
          {user.avatarUrl ? (
            <img src={user.avatarUrl} alt="" className="w-full h-full object-cover" />
          ) : (
            user.name?.charAt(0) || '?'
          )}
        </div>
        <span className="text-sm text-[#1A1A1A]">{user.name}</span>
        <a
          href="/api/auth/logout"
          className="text-xs text-[#8590A6] hover:text-[#0066FF] transition-colors"
        >
          退出
        </a>
      </div>
    );
  }

  return (
    <a
      href="/api/auth/login"
      className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#0066FF] text-white rounded-full hover:bg-[#0052CC] transition-colors text-sm font-medium"
    >
      登录参战
    </a>
  );
}
