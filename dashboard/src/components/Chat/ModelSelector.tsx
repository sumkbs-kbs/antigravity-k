/**
 * ModelSelector — Dropdown for selecting AI model
 */

import React, { useEffect, useState } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { fetchModels, type ModelInfo } from '../../api/client';

const ModelSelector: React.FC = () => {
  const { selectedModel, setSelectedModel } = useChatStore();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchModels();
        setModels(data);
        useChatStore.getState().setModels(data);
      } catch (err) {
        console.error('Failed to load models:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const grouped: Record<string, ModelInfo[]> = {};
  models.forEach(m => {
    const role = m.role || 'other';
    if (!grouped[role]) grouped[role] = [];
    grouped[role].push(m);
  });

  const roleOrder = ['reasoning', 'coding', 'vision', 'embedding'];
  const roleLabels: Record<string, string> = {
    reasoning: '🧠 Reasoning',
    coding: '💻 Coding',
    vision: '👁️ Vision',
    embedding: '📐 Embedding',
  };

function extractQuant(modelId: string): string {
  if (!modelId) return 'GGUF';
  if (modelId.includes('UD-Q4_K_XL')) return 'UD-Q4_K_XL';
  if (modelId.includes('Q5_K_M')) return 'Q5_K_M';
  if (modelId.includes('Q4_K_M')) return 'Q4_K_M';
  if (modelId.includes('Q8_0')) return 'Q8_0';
  if (modelId.includes('4bit') || modelId.includes('mlx')) return 'MLX 4b';
  if (modelId.includes('FP16')) return 'FP16';
  if (modelId.includes('gpt') || modelId.includes('claude')) return 'API';
  return 'Fast';
}

  return (
    <div className="unsloth-model-selector-wrap">
      <select
        className="glass-select"
        value={selectedModel}
        onChange={e => setSelectedModel(e.target.value)}
        disabled={loading}
        aria-label="AI 모델 선택"
      >
        {loading ? (
          <option>Loading models...</option>
        ) : (
          <>
            {roleOrder.map(role => {
              const list = grouped[role];
              if (!list?.length) return null;
              return (
                <optgroup key={role} label={roleLabels[role] || role}>
                  {list.map(m => (
                    <option key={m.id} value={m.id}>{m.id}</option>
                  ))}
                </optgroup>
              );
            })}
          </>
        )}
      </select>
      <span className="unsloth-quant-chip" title="모델 가속/양자화 포맷">
        {extractQuant(selectedModel)}
      </span>
    </div>
  );
};

export default ModelSelector;
