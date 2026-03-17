export interface User {
  id: string;
  name: string;
  avatarUrl: string | null;
}

export interface Message {
  agent: string;
  content: string;
  phase: string;
  target_agent?: string;
  defected?: boolean;
  old_label?: string;
  new_label?: string;
}

export interface Bet {
  id: string;
  agentName: string;
  option: string;
  amount: number;
  confidence: number;
  reasoning: string | null;
  won: boolean | null;
}

export interface OptionAnalysis {
  score: number;
  strength: string;
  weakness: string;
  key_evidence?: string;
  data_support?: string;
}

export interface Judgment {
  reasoning: string;
  option_analysis?: Record<string, OptionAnalysis>;
  mvp: string;
  mvp_reason?: string;
  highlights: string[];
  scores: Record<string, Record<string, number>>;
  data_sources?: string[];
  confidence_level?: string;
  dissenting_opinion?: string;
  total_pool?: number;
  loser_pool?: number;
  payouts: Record<string, { bet: number; profit: number; net: number; result: string }>;
}

export interface Debate {
  id: string;
  title: string;
  description: string;
  options: string[];
  option_prices?: Record<string, number>;
  status: string;
  phase: number;
  result: string | null;
  transcript: Message[];
  bets: Bet[];
  judgment?: Judgment | null;
  createdAt: string;
}

export interface OptionStat {
  name: string;
  bets: Bet[];
  total: number;
  pct: number;
  price: number;
  isWinner: boolean;
  isLoser: boolean;
  color: string;
}

export interface Holding {
  id: string;
  debate_id: string;
  debate_title: string;
  option_key: string;
  option_label: string;
  quantity: number;
  buy_price: number;
  total_cost: number;
  current_price?: number;
  current_value?: number;
  pnl?: number;
  pnl_pct?: number;
  status: 'active' | 'settled_win' | 'settled_lose';
  bought_at: string;
  debate_status?: string;
  result?: string;
}

export interface Transaction {
  id: string;
  type: 'buy' | 'settle_win' | 'settle_lose';
  debate_id: string;
  option_label: string;
  amount: number;
  shares: number;
  price_per_share: number;
  timestamp: string;
}

export interface Wallet {
  user_id: string;
  user_name: string;
  balance: number;
  net_worth: number;
  initial_balance: number;
  total_pnl: number;
  holdings: Holding[];
  transactions: Transaction[];
}
