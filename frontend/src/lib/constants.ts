export const AGENT_AVATARS: Record<string, { emoji: string; color: string; bg: string }> = {
  '🐂牛哥': { emoji: '🐂', color: '#E53935', bg: '#FFEBEE' },
  '🐻熊总': { emoji: '🐻', color: '#1E88E5', bg: '#E3F2FD' },
  '🦊狐师': { emoji: '🦊', color: '#F57C00', bg: '#FFF3E0' },
  '🦉鸮博士': { emoji: '🦉', color: '#2E7D32', bg: '#E8F5E9' },
  '🎲梭哈王': { emoji: '🎲', color: '#7B1FA2', bg: '#F3E5F5' },
  '⚖️刘看山': { emoji: '⚖️', color: '#37474F', bg: '#ECEFF1' },
};

export function getAgent(name: string) {
  return AGENT_AVATARS[name] || { emoji: '👤', color: '#666', bg: '#f5f5f5' };
}

export const OPTION_COLORS = ['#0066FF', '#F1403C', '#00C853', '#9C27B0', '#FF6D00', '#00BCD4'];

export const AGENT_COLORS: Record<string, string> = {
  '🐂牛哥': '#E53935',
  '🐻熊总': '#1E88E5',
  '🦊狐师': '#F57C00',
  '🦉鸮博士': '#2E7D32',
  '🎲梭哈王': '#7B1FA2',
};

export const DEFAULT_ROSTER = [
  { emoji: '🐂', name: '牛哥', desc: '永远乐观，重仓梭哈', color: '#E53935' },
  { emoji: '🐻', name: '熊总', desc: '永远悲观，专挑毛病', color: '#1E88E5' },
  { emoji: '🦊', name: '狐师', desc: '找漏洞，抬杠专家', color: '#F57C00' },
  { emoji: '🦉', name: '鸮博士', desc: '数据说话，只认证据', color: '#2E7D32' },
  { emoji: '🎲', name: '梭哈王', desc: '跟着直觉走，要么全押', color: '#7B1FA2' },
];
