import React, { useCallback, useEffect, useState } from 'react';
import { fetchModelOperations, type ModelOperationsStatus } from '../../api/client';
import GlassPanel from './GlassPanel';

const formatRate = (value: number | null): string => (value === null ? '-' : `${Math.round(value * 100)}%`);

const ModelOperationsPanel: React.FC = () => {
  const [status, setStatus] = useState<ModelOperationsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadStatus = useCallback(async (refresh = false) => {
    setLoading(true);
    setError('');
    try {
      setStatus(await fetchModelOperations(refresh));
    } catch {
      setError('모델 운영 상태를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const metrics = status?.quality_calibration.operational_metrics ?? [];
  const capabilities = Object.values(status?.provider_capabilities ?? {})
    .filter(capability => capability.is_local)
    .sort((left, right) => {
      const leftIsPreferred = left.model === 'qwen3.6:latest';
      const rightIsPreferred = right.model === 'qwen3.6:latest';
      if (leftIsPreferred === rightIsPreferred) return left.model.localeCompare(right.model);
      return leftIsPreferred ? -1 : 1;
    });
  const eligibleModels = status?.quality_calibration.eligible_models.length ?? 0;

  return (
    <GlassPanel title="모델 운영 상태" variant="section" className="settings-section model-operations-panel">
      <div className="model-ops-toolbar">
        <span className="model-ops-note">로컬 런타임 준비 상태와 실제 작업 성과</span>
        <button
          type="button"
          className="model-ops-refresh"
          onClick={() => void loadStatus(true)}
          disabled={loading}
          aria-label="모델 운영 상태 새로고침"
          title="모델 운영 상태 새로고침"
        >
          ↻
        </button>
      </div>

      {loading && status === null ? (
        <div className="model-ops-empty">모델 운영 상태 불러오는 중...</div>
      ) : error ? (
        <div className="model-ops-error" role="alert">{error}</div>
      ) : (
        <>
          <div className="model-ops-kpis" aria-label="모델 운영 요약">
            <div>
              <span>Quality calibration</span>
              <strong>{status?.quality_calibration.enabled ? 'active' : 'off'}</strong>
            </div>
            <div>
              <span>Eligible models</span>
              <strong>{eligibleModels}</strong>
            </div>
            <div>
              <span>Observed tasks</span>
              <strong>{metrics.reduce((total, metric) => total + metric.outcome_count, 0)}</strong>
            </div>
          </div>

          <div className="model-ops-section">
            <div className="model-ops-section-title">Provider readiness</div>
            {capabilities.length === 0 ? (
              <div className="model-ops-empty">등록된 provider 상태가 없습니다.</div>
            ) : (
              <div className="model-ops-table-wrap">
                <table className="model-ops-table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Provider</th>
                      <th>Runtime</th>
                      <th>Native tools</th>
                      <th>Probe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {capabilities.map(capability => (
                      <tr key={capability.model} className={capability.model === 'qwen3.6:latest' ? 'model-ops-priority' : undefined}>
                        <td className="model-ops-model" data-label="Model">{capability.model}</td>
                        <td data-label="Provider">{capability.provider}</td>
                        <td data-label="Runtime"><span className={`model-ops-chip ${capability.runtime_status}`}>{capability.runtime_status}</span></td>
                        <td data-label="Native tools"><span className={`model-ops-chip ${capability.native_tool_calling}`}>{capability.native_tool_calling}</span></td>
                        <td className="model-ops-source" data-label="Probe" title={capability.detail}>{capability.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="model-ops-section">
            <div className="model-ops-section-title">Observed task quality</div>
            {metrics.length === 0 ? (
              <div className="model-ops-empty">누적된 작업 결과가 없습니다.</div>
            ) : (
              <div className="model-ops-table-wrap">
                <table className="model-ops-table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Samples</th>
                      <th>Success</th>
                      <th>Tool accuracy</th>
                      <th>Retry</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.map(metric => (
                      <tr key={metric.model}>
                        <td className="model-ops-model" data-label="Model">{metric.model}</td>
                        <td data-label="Samples">{metric.outcome_count}</td>
                        <td data-label="Success">{formatRate(metric.task_success_rate)}</td>
                        <td data-label="Tool accuracy">{formatRate(metric.tool_accuracy)}</td>
                        <td data-label="Retry">{formatRate(metric.retry_rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </GlassPanel>
  );
};

export default ModelOperationsPanel;
