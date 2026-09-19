/**
 * ChatPage quantization quality badge tests (Phase 15)
 * =====================================================
 * 모델 선택 팝오버의 `badge-quant` 칩이 Model Hub와 동일한 quantQuality
 * 등급 체계(`q-{level}` 변형 + 툴팁)를 사용하는지 검증한다.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChatPage from '../ChatPage';
import * as client from '../../../api/client';
import { useChatStore } from '../../../stores/chatStore';
import type { LocalModelItem } from '../../../api/client';

function makeModel(overrides: Partial<LocalModelItem>): LocalModelItem {
  return {
    id: 'test-model',
    name: 'test-model',
    provider: 'unsloth',
    role: 'reasoning',
    parameter_count_b: 4.0,
    is_local: true,
    status: 'cached',
    disk_path: '/path/to/gguf',
    disk_size_gb: 2.5,
    quantization: '',
    source: 'huggingface_cache',
    ...overrides,
  };
}

function renderChatPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>
  );
}

async function openModelPopover() {
  fireEvent.click(screen.getByRole('button', { name: /모델 선택/i }));
  await waitFor(() => {
    expect(screen.getByText(/본 PC 전체 로컬 모델/)).toBeInTheDocument();
  });
}

describe('ChatPage badge-quant quality grades (Phase 15)', () => {
  const fetchLocalModelsSpy = vi.spyOn(client, 'fetchLocalModels');

  beforeEach(() => {
    fetchLocalModelsSpy.mockResolvedValue({
      ok: true,
      total: 3,
      recommended_default: 'Qwen3.8-27B-UD-Q4_K_XL',
      models: [
        makeModel({
          id: 'Qwen3.8-27B-UD-Q4_K_XL',
          name: 'Qwen3.8-27B-UD-Q4_K_XL',
          quantization: 'UD-Q4_K_XL',
          disk_size_gb: 16.8,
        }),
        makeModel({
          id: 'Llama-3.2-1B-Instruct-4bit',
          name: 'Llama-3.2-1B-Instruct-4bit',
          provider: 'mlx',
          quantization: '4bit',
          disk_size_gb: 0.7,
        }),
        makeModel({
          id: 'qwen3.8:latest',
          name: 'qwen3.8:latest',
          provider: 'ollama',
          status: 'running',
          quantization: '',
          disk_size_gb: 0,
        }),
      ],
      message: '3 local models detected',
    });
  });

  afterEach(() => {
    fetchLocalModelsSpy.mockReset();
    useChatStore.setState({
      messages: [],
      activeSession: null,
      isStreaming: false,
    });
  });

  it('renders balanced grade class and tooltip for UD-Q4_K_XL unsloth model', async () => {
    renderChatPage();
    await openModelPopover();

    const chip = await screen.findByText('UD-Q4_K_XL');
    expect(chip).toHaveClass('badge-quant', 'q-balanced');
    expect(chip).toHaveAttribute('title', 'UD-Q4_K_XL — 균형 — 크기·품질 스위트스팟');
    // Phase 39: 칩 내부 한 글자 등급 아이콘 (::before — data-grade로 단언)
    expect(chip).toHaveAttribute('data-grade', 'B');
  });

  it('renders the same balanced grade for the 4bit MLX model (parity with Model Hub)', async () => {
    renderChatPage();
    await openModelPopover();

    const chip = await screen.findByText('4bit');
    expect(chip).toHaveClass('badge-quant', 'q-balanced');
    expect(chip).toHaveAttribute('title', '4bit — 균형 — 크기·품질 스위트스팟');
  });

  it('omits the quant chip entirely when quantization is empty (running ollama model)', async () => {
    renderChatPage();
    await openModelPopover();

    await screen.findByText('qwen3.8:latest');
    // 빈 quantization은 칩이 아예 렌더링되지 않는다 (unknown 등급도 표시 안 함 — 기존 동작 유지)
    expect(screen.queryByText(/^badge-quant/)).toBeNull();
    const runningRow = screen.getByText('qwen3.8:latest').closest('.model-choice-row');
    expect(runningRow?.querySelector('.badge-quant')).toBeNull();
  });
});
