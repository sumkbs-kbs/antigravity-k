/**
 * ModelSelector — Dropdown for selecting AI model
 */
// @ts-nocheck


import React, { useEffect, useState } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { useUiStore } from '../../stores/uiStore';
import { fetchModels, type ModelInfo } from '../../api/client';

const ModelSelector: React.FC = () => {
  const { selectedModel, setSelectedModel } = useChatStore();
  const { addToast } = useUiStore();
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

  return (
    <select
      className="glass-select"
      value={selectedModel}
      onChange={e => setSelectedModel(e.target.value)}
      disabled={loading}
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
  );
};

export default ModelSelector;
