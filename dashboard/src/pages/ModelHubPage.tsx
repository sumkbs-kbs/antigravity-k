/**
 * ModelHubPage — Unsloth Desktop Inspired Model Hub & Discovery
 * ===============================================================
 * Explore, download, swap, and manage state-of-the-art LLMs, Vision,
 * and MLX/GGUF models with automatic VRAM requirements & quantizations.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useUiStore } from '../stores/uiStore';
import { fetchLocalModels, loadModel, type LocalModelItem } from '../api/client';

interface HubDisplayModel {
  id: string;
  name: string;
  provider: string;
  category: 'all' | 'running' | 'unsloth' | 'mlx' | 'embedding' | 'llm';
  params: string;
  context: string;
  quantization: string;
  vram: string;
  diskSize: string;
  diskPath: string;
  description: string;
  status: 'running' | 'installed' | 'cached';
  isLocal: boolean;
}

export const ModelHubPage: React.FC = () => {
  const { selectedModel, setSelectedModel } = useChatStore();
  const { addToast } = useUiStore();
  const [filterCategory, setFilterCategory] = useState<'all' | 'running' | 'unsloth' | 'mlx' | 'embedding' | 'llm'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [localModels, setLocalModels] = useState<LocalModelItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingModelId, setLoadingModelId] = useState<string | null>(null);

  const loadModels = useCallback(async (refresh = false) => {
    setIsLoading(true);
    try {
      const res = await fetchLocalModels(refresh);
      if (res.ok && res.models) {
        setLocalModels(res.models);
      }
    } catch (err) {
      console.error('Failed to load local models in ModelHub:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadModels(false);
  }, [loadModels]);

  const handleSelectModel = async (modelId: string) => {
    setLoadingModelId(modelId);
    try {
      const res = await loadModel(modelId);
      if (res.ok) {
        setSelectedModel(modelId);
        addToast(`✅ 모델이 성공적으로 로드되었습니다: ${modelId.split('/').pop()}`, 'success');
        void loadModels(false);
      } else {
        addToast(`❌ 모델 로드 실패: ${res.message || '알 수 없는 오류'}`, 'error');
      }
    } catch (err: any) {
      addToast(`❌ 모델 로드 오류: ${err?.message || String(err)}`, 'error');
    } finally {
      setLoadingModelId(null);
    }
  };

  // Convert LocalModelItem to HubDisplayModel
  const displayModels: HubDisplayModel[] = localModels.map((m) => {
    let cat: 'all' | 'running' | 'unsloth' | 'mlx' | 'embedding' | 'llm' = 'llm';
    if (m.status === 'running') cat = 'running';
    else if (m.provider === 'unsloth') cat = 'unsloth';
    else if (m.provider === 'mlx') cat = 'mlx';
    else if (m.role === 'embedding') cat = 'embedding';

    const paramStr = m.parameter_count_b > 0
      ? `${m.parameter_count_b}B`
      : (m.disk_size_gb > 0 ? `${m.disk_size_gb} GB` : 'Local');

    return {
      id: m.id,
      name: m.name || m.id,
      provider: m.provider.toUpperCase(),
      category: cat,
      params: paramStr,
      context: m.context_length ? `${Math.round(m.context_length / 1024)}K` : 'Auto',
      quantization: m.quantization || (m.status === 'running' ? 'Active' : 'N/A'),
      vram: m.parameter_count_b > 0 ? `~${Math.round(m.parameter_count_b * 0.7)} GB` : (m.disk_size_gb > 0 ? `~${Math.round(m.disk_size_gb)} GB` : 'N/A'),
      diskSize: m.disk_size_gb > 0 ? `${m.disk_size_gb} GB` : (m.status === 'running' ? 'Ollama 메모리' : '로컬 디스크'),
      diskPath: m.disk_path || '',
      description: m.description || `본 PC에 설치된 ${m.provider} 로컬 모델.`,
      status: (m.status as any) || 'installed',
      isLocal: true,
    };
  });

  const filteredModels = displayModels.filter((m) => {
    if (filterCategory !== 'all') {
      if (filterCategory === 'running' && m.status !== 'running') return false;
      if (filterCategory === 'unsloth' && m.provider !== 'UNSLOTH') return false;
      if (filterCategory === 'mlx' && m.provider !== 'MLX') return false;
      if (filterCategory === 'embedding' && m.category !== 'embedding') return false;
      if (filterCategory === 'llm' && (m.category === 'embedding' || m.provider === 'MLX')) return false;
    }
    if (
      searchQuery.trim() &&
      !m.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !m.id.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !m.provider.toLowerCase().includes(searchQuery.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  return (
    <div className="unsloth-hub-container">
      {/* Header */}
      <header className="unsloth-hub-header">
        <div className="hub-title-section">
          <div className="hub-icon">📦</div>
          <div>
            <div className="flex-align-center gap-8">
              <h1 className="hub-title">Model Hub</h1>
              <span className="hub-badge">UNSLOTH & LOCAL ECOSYSTEM</span>
            </div>
            <p className="hub-sub">
              본 PC에 설치된 Ollama 모델, Unsloth GGUF 다운로드 모델, Apple MLX 캐시 모델을 실시간으로 감지하고 원클릭으로 로드합니다.
            </p>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="hub-filter-bar">
          <div className="hub-search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="모델명, 아키텍처 또는 공급자 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="hub-search-input"
            />
          </div>

          <div className="hub-category-pills">
            {[
              { id: 'all', label: `전체 (${displayModels.length})` },
              { id: 'running', label: `🟢 실행 중 (${displayModels.filter((m) => m.status === 'running').length})` },
              { id: 'unsloth', label: `🦥 Unsloth GGUF (${displayModels.filter((m) => m.provider === 'UNSLOTH').length})` },
              { id: 'mlx', label: `Apple MLX (${displayModels.filter((m) => m.provider === 'MLX').length})` },
              { id: 'embedding', label: `Embedding (${displayModels.filter((m) => m.category === 'embedding').length})` },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                className={`hub-cat-btn ${filterCategory === cat.id ? 'active' : ''}`}
                onClick={() => setFilterCategory(cat.id as any)}
              >
                {cat.label}
              </button>
            ))}

            <button
              type="button"
              className="hub-cat-btn"
              style={{ marginLeft: 'auto' }}
              disabled={isLoading}
              onClick={() => void loadModels(true)}
              title="본 PC 로컬 모델 다시 검색"
            >
              {isLoading ? '스캔 중...' : '↻ PC 모델 재검색'}
            </button>
          </div>
        </div>
      </header>

      {/* Model Grid */}
      <div className="hub-models-grid">
        {filteredModels.length === 0 ? (
          <div className="model-empty-notice" style={{ gridColumn: '1 / -1', padding: '40px 20px' }}>
            {isLoading
              ? '본 PC의 로컬 모델을 스캔하고 있습니다...'
              : '해당 조건에 맞는 로컬 모델을 찾을 수 없습니다.'}
          </div>
        ) : (
          filteredModels.map((model) => {
            const isActive = selectedModel === model.id;

            return (
              <div key={model.id} className={`hub-card ${isActive ? 'active-model' : ''}`}>
                <div className="hub-card-top">
                  <div className="hub-model-identity">
                    <span className={`provider-tag ${model.provider.toLowerCase()}`}>{model.provider}</span>
                    <h2 className="model-display-name">{model.name}</h2>
                  </div>
                  {model.status === 'running' ? (
                    <span className="popular-badge" style={{ background: '#dcfce7', color: '#15803d' }}>
                      🟢 실행 중
                    </span>
                  ) : (
                    <span className="spec-badge" style={{ fontSize: '10px' }}>
                      📦 로컬 캐시
                    </span>
                  )}
                  {isActive && <span className="active-badge">● Active</span>}
                </div>

                <p className="model-desc-text">{model.description}</p>

                {/* Specs Chips */}
                <div className="model-specs-row">
                  <div className="spec-badge">
                    <span className="spec-key">Params</span>
                    <span className="spec-val">{model.params}</span>
                  </div>
                  <div className="spec-badge">
                    <span className="spec-key">디스크 용량</span>
                    <span className="spec-val highlight">{model.diskSize}</span>
                  </div>
                  <div className="spec-badge">
                    <span className="spec-key">양자화</span>
                    <span className="spec-val">{model.quantization}</span>
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="hub-card-footer">
                  <div className="card-status-info">
                    <span className="status-indicator local">
                      ✓ 로컬 준비됨
                    </span>
                  </div>
                  <div className="card-actions">
                    <button
                      type="button"
                      className={`hub-action-btn ${isActive ? 'current' : 'swap'}`}
                      disabled={loadingModelId === model.id}
                      onClick={() => void handleSelectModel(model.id)}
                    >
                      {loadingModelId === model.id
                        ? '⏳ 런타임 로딩 중...'
                        : (isActive ? '현재 사용 중' : '⚡ 모델 활성화 (Load)')}
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ModelHubPage;
