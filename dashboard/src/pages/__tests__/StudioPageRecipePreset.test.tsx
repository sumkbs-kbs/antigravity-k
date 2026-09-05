/**
 * StudioPage recipe preset selector tests (Phase 24)
 * ====================================================
 * STEP 4 하이퍼파라미터 필드가 백엔드 레시피 카탈로그의 감사된 값으로
 * 채워지는지 검증한다. 단일 진실원: engine/data_recipes.py의 RECIPES.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import StudioPage from '../StudioPage';
import * as client from '../../api/client';
import type { TrainingRecipe } from '../../api/client';

vi.mock('../../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return {
    ...actual,
    fetchTrainingRecipes: vi.fn(),
  };
});

const fetchTrainingRecipesMock = vi.mocked(client.fetchTrainingRecipes);

const RECIPES: TrainingRecipe[] = [
  {
    name: 'pdf-qa-sft',
    title: 'PDF Q&A SFT',
    description: 'PDF 문서를 Q&A 쌍으로 변환해 학습',
    source_hint: 'pdf',
    format: 'chat',
    min_records: 5,
    hyperparameters: { iterations: 500, learning_rate: '2e-5', batch_size: 2 },
  },
  {
    name: 'preference-dpo',
    title: 'Preference DPO',
    description: '선호 쌍 기반 정렬 학습',
    source_hint: 'harvest_pairs',
    format: 'dpo',
    min_records: 20,
    hyperparameters: { iterations: 400, learning_rate: '5e-6', batch_size: 4, num_train_epochs: 1 },
  },
];

function renderStudio() {
  return render(
    <MemoryRouter>
      <StudioPage />
    </MemoryRouter>
  );
}

async function goToStep4() {
  // STEP 1 → 2 → 3 → 4 이동 (스텝 이동 버튼 텍스트 기반)
  fireEvent.click(screen.getByRole('button', { name: /모델 선택 완료|다음/i }));
  fireEvent.click(screen.getByRole('button', { name: /다음: 데이터셋/i }));
  fireEvent.click(screen.getByRole('button', { name: /다음: 하이퍼파라미터/i }));
  await screen.findByText('4. 하이퍼파라미터 튜닝 (Hyperparameters)');
}

describe('StudioPage STEP 4 recipe presets (Phase 24)', () => {
  beforeEach(() => {
    fetchTrainingRecipesMock.mockReset();
    fetchTrainingRecipesMock.mockResolvedValue({ ok: true, recipes: RECIPES });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads the recipe catalog and applies audited values to the fields', async () => {
    renderStudio();
    await goToStep4();

    const select = screen.getByLabelText(/데이터 레시피 프리셋/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'pdf-qa-sft' } });

    await waitFor(() => {
      // learning_rate '2e-5'가 LR 필드에 채워짐
      expect(screen.getByDisplayValue('2e-5')).toBeInTheDocument();
      expect(screen.getByDisplayValue('2')).toBeInTheDocument(); // batch_size
      expect(screen.getByDisplayValue('500')).toBeInTheDocument(); // iterations
    });
    // 감사된 값 요약 표시
    expect(screen.getByText(/iterations=500 · learning_rate=2e-5 · batch_size=2|learning_rate=2e-5/)).toBeInTheDocument();
  });

  it('allows manual entry when no preset is selected and still renders fields', async () => {
    renderStudio();
    await goToStep4();

    const select = screen.getByLabelText(/데이터 레시피 프리셋/i) as HTMLSelectElement;
    expect(select.value).toBe('');
    // 기본(Unsloth 권장) 값 유지 — rank는 select, alpha/lr은 input
    expect(screen.getByLabelText(/LoRA Rank/i)).toHaveValue('16');
    expect(screen.getByDisplayValue('2e-4')).toBeInTheDocument();
    expect(screen.getByDisplayValue('32')).toBeInTheDocument();
  });

  it('keeps the UI usable when the catalog API fails', async () => {
    fetchTrainingRecipesMock.mockRejectedValue(new Error('catalog down'));
    renderStudio();
    await goToStep4();

    // 프리셋 없이 필드만 존재 — 페이지 크래시 없음
    expect(screen.getByLabelText(/LoRA Rank/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Learning Rate/i)).toBeInTheDocument();
  });
});
