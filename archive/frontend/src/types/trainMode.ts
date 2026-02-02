/**
 * Type definitions for Train mode
 */

// Strategy information
export interface StrategyMetrics {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
}

export interface Strategy {
  name: string;
  description: string;
  symbol: string;
  timeframe: string;
  indicators: any[];
  fuzzyConfig: Record<string, any>;
  trainingStatus: 'untrained' | 'training' | 'trained' | 'failed';
  availableVersions: number[];
  latestVersion?: number;
  latestTrainingDate?: string;
  latestMetrics?: StrategyMetrics;
}

// Backtest types
export interface BacktestRequest {
  strategyName: string;
  symbol: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  initialCapital?: number;
  commission?: number;
  slippage?: number;
  dataMode?: string;
}

export interface ProgressInfo {
  percentage: number;
  current_step: string;
  items_processed?: number;
  items_total?: number;
}

export interface BacktestStatus {
  id: string;
  strategyName: string;
  status: 'idle' | 'starting' | 'running' | 'completed' | 'failed';
  progress: number; // Legacy - keep for backward compatibility
  progressInfo?: ProgressInfo; // New enhanced progress information
  startedAt: string | null;
  error?: string;
  warnings?: string[];
  errors?: string[];
}

export interface BacktestMetrics {
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
}

export interface BacktestSummary {
  initialCapital: number;
  finalValue: number;
  totalPnl: number;
  winningTrades: number;
  losingTrades: number;
}

export interface BacktestResults {
  backtestId: string;
  strategyName: string;
  symbol: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  metrics: BacktestMetrics;
  summary: BacktestSummary;
}

export interface Trade {
  tradeId?: string;
  entryTime: string;
  exitTime: string;
  side: 'BUY' | 'SELL';
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  pnl: number;
  pnlPercent: number;
  entryReason?: string;
  exitReason?: string;
}

export interface EquityCurve {
  timestamps: string[];
  values: number[];
  drawdowns: number[];
}