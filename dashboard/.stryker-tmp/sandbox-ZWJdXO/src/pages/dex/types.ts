/**
 * Data Extraction — Shared Types & Constants
 * ===========================================
 */
// @ts-nocheck


export interface ExtractedStock {
  name?: string;
  ticker?: string;
  close_price?: number;
  open_price?: number;
  high_price?: number;
  low_price?: number;
  change_percent?: number;
  change_amount?: number;
  volume?: number;
}

export interface ExtractedWeather {
  location?: string;
  temperature?: number;
  humidity?: number;
  condition?: string;
}

export interface ExtractedExchange {
  currency_pair?: string;
  rate?: number;
  change_percent?: number;
}

export interface ExtractionData {
  query: string;
  search_length: number;
  has_top1_json: boolean;
  extracted: {
    stock_prices: ExtractedStock[];
    weather: ExtractedWeather[];
    exchange_rates: ExtractedExchange[];
    dates_found: string[];
  };
  extraction_log?: string;
}

export interface MetricsData {
  total_calls?: number;
  stock_attempts?: number;
  stock_success?: number;
  weather_attempts?: number;
  weather_success?: number;
  exchange_attempts?: number;
  exchange_success?: number;
  speculative_filtered?: number;
  success_rates?: {
    overall?: number;
    stock?: number;
    weather?: number;
    exchange?: number;
  };
}

export interface ABTestReport {
  avg_accuracy: number;
  avg_duration_ms: number;
  total_cases: number;
  passed: number;
  failed: number;
  by_tag?: Record<string, number>;
  comparisons?: ABTestCase[];
}

export interface ABTestCase {
  case_name: string;
  accuracy_pct: number;
  fields_matched: number;
  fields_total: number;
  duration_ms: number;
  has_expected: boolean;
}

/* ─── Pipeline Step Config ──────────────────────────────────── */

export interface PipelineStep {
  id: string;
  icon: string;
  label: string;
  desc: string;
}

export const METRICS_BASE: PipelineStep[] = [
  { id: 'search', icon: '🔍', label: '웹 검색 실행', desc: 'Self-Hosted → TOP 1' },
  { id: 'top1_json', icon: '📋', label: 'TOP 1 JSON 추출', desc: 'Markdown → Brace Matching' },
  { id: 'ticker', icon: '🏷️', label: '종목명/코드 추출', desc: '패턴 → 검증' },
  { id: 'manwon', icon: '💹', label: '만원/억원 패턴', desc: '만원 → 억원 변환' },
  { id: 'extract', icon: '📊', label: '구조화 데이터', desc: '주가+날씨+환율+날짜' },
];

export type PipelineStatusType = 'idle' | 'loading' | 'success' | 'fail' | 'partial';

export const STATUS_ICONS: Record<PipelineStatusType, string> = {
  idle: '⚪', loading: '⏳', success: '✅', fail: '❌', partial: '⚠️',
};
