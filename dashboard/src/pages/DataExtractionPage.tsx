/**
 * DataExtractionPage — Data Extraction Dashboard
 * ================================================
 * Orchestrator component — delegates to sub-components in ./dex/
 */

import React, { useState, useCallback, useEffect } from 'react';
import { ExtractionData, MetricsData, ABTestReport } from './dex/types';
import MetricsBar from './dex/MetricsBar';
import SearchHeader from './dex/SearchHeader';
import ABTestSection from './dex/ABTestSection';
import PipelineStatus from './dex/PipelineStatus';
import StockPanel from './dex/StockPanel';
import WeatherExchangePanel from './dex/WeatherExchangePanel';
import BottomPanels from './dex/BottomPanels';

type MetricsResponse = { ok?: boolean; metrics?: MetricsData };
type ExtractionResponse = ExtractionData & { ok?: boolean };
type ABTestResponse = { ok?: boolean; report?: ABTestReport };

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function readStoredResult(): ExtractionData | null {
  try {
    const saved = sessionStorage.getItem('dex_last_result');
    if (!saved) return null;
    const parsed: unknown = JSON.parse(saved);
    return parsed && typeof parsed === 'object' ? parsed as ExtractionData : null;
  } catch {
    return null;
  }
}

const DataExtractionPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<ExtractionData | null>(readStoredResult);
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [abtestResults, setAbtestResults] = useState<ABTestReport | null>(null);
  const [abtestRunning, setAbtestRunning] = useState(false);

  const loadMetrics = useCallback(async () => {
    try {
      const res = await fetch('/api/search/extraction-metrics');
      if (!res.ok) throw new Error(`Metrics request failed with status ${res.status}`);
      const data = await res.json() as MetricsResponse;
      if (data.ok === true && data.metrics) setMetrics(data.metrics);
    } catch (error) {
      console.error('Metrics load failed:', describeError(error));
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadMetrics(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadMetrics]);

  const handleSearch = useCallback(async () => {
    if (!query.trim() || searching) return;
    setSearching(true);
    try {
      const res = await fetch('/api/search/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) throw new Error(`Extraction request failed with status ${res.status}`);
      const data = await res.json() as ExtractionResponse;
      if (data.ok === true) {
        setResult(data);
        sessionStorage.setItem('dex_last_result', JSON.stringify(data));
      }
    } catch (error: unknown) {
      console.error('Search failed:', describeError(error));
    } finally {
      setSearching(false);
    }
  }, [query, searching]);

  const handleABTest = async () => {
    setAbtestRunning(true);
    try {
      const res = await fetch('/api/search/ab-test/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version_label: 'dashboard' }),
      });
      if (!res.ok) throw new Error(`A/B test request failed with status ${res.status}`);
      const data = await res.json() as ABTestResponse;
      if (data.ok === true && data.report) setAbtestResults(data.report);
    } catch (error) {
      console.error('A/B test failed:', describeError(error));
    }
    setAbtestRunning(false);
  };

  const sp = result?.extracted?.stock_prices || [];
  const weather = result?.extracted?.weather || [];
  const exchange = result?.extracted?.exchange_rates || [];

  return (
    <div className="dex-page" style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      overflowY: 'auto', paddingBottom: 60,
    }}>
      <MetricsBar metrics={metrics} />
      <SearchHeader
        query={query}
        searching={searching}
        onQueryChange={setQuery}
        onSearch={handleSearch}
      />
      <ABTestSection
        results={abtestResults}
        running={abtestRunning}
        onRun={handleABTest}
      />

      {/* Main Content */}
      <div id="dex-content" style={{ flex: 1, padding: '24px 32px' }}>
        {!result && !searching ? (
          <div className="empty-state-container">
            <span style={{ fontSize: 64, opacity: 0.3 }}>🔬</span>
            <h2 className="empty-state-title">데이터 추출 대시보드</h2>
            <p className="empty-state-subtitle">
              위 검색창에 질문을 입력하면<br />
              <strong>TOP 1 JSON 추출</strong> → <strong>종목명 검증</strong> → <strong>만원/억원 변환</strong> 과정을 실시간으로 시각화합니다.
            </p>
          </div>
        ) : searching ? (
          <LoadingState />
        ) : result ? (
          <ResultView result={result} stocks={sp} weather={weather} exchange={exchange} />
        ) : null}
      </div>
    </div>
  );
};

/* ─── Loading State ──────────────────────────────────────────── */

const LoadingState: React.FC = () => (
  <div style={{
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    height: '50vh', gap: 24,
  }}>
    <div style={{
      width: 48, height: 48,
      border: '3px solid var(--glass-border)',
      borderTopColor: 'var(--accent-color)',
      borderRadius: '50%',
      animation: 'dex-spin 0.8s linear infinite',
    }} />
    <div style={{ textAlign: 'center' }}>
      <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>검색 + 데이터 추출 중...</p>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
        WebSearchTool → DataExtractor → 구조화 데이터
      </p>
    </div>
    {/* Skeleton Cards */}
    <div style={{ width: '100%', maxWidth: 600, marginTop: 8 }}>
      <div className="skeleton skeleton-card" style={{ height: 60 }} />
      <div className="skeleton skeleton-card" style={{ height: 80 }} />
      <div className="skeleton skeleton-card" style={{ height: 60, width: '70%' }} />
    </div>
  </div>
);

/* ─── Result View ────────────────────────────────────────────── */

interface ResultViewProps {
  result: ExtractionData;
  stocks: ExtractionData['extracted']['stock_prices'];
  weather: ExtractionData['extracted']['weather'];
  exchange: ExtractionData['extracted']['exchange_rates'];
}

const ResultView: React.FC<ResultViewProps> = ({ result, stocks, weather, exchange }) => (
  <>
    <div className="dex-card-enter">
      <PipelineStatus result={result} />
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }} className="dex-card-enter">
      <StockPanel stocks={stocks} />
      <WeatherExchangePanel weather={weather} exchange={exchange} />
    </div>
    <div className="dex-card-enter">
      <BottomPanels result={result} />
    </div>
  </>
);

export default DataExtractionPage;
