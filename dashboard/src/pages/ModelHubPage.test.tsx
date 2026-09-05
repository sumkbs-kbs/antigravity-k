import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ModelHubPage from './ModelHubPage';
import * as client from '../api/client';

describe('ModelHubPage', () => {
  beforeEach(() => {
    vi.spyOn(client, 'fetchLocalModels').mockResolvedValue({
      ok: true,
      total: 3,
      recommended_default: 'qwen3.8:latest',
      models: [
        {
          id: 'qwen3.8:latest',
          name: 'qwen3.8:latest',
          provider: 'ollama',
          role: 'reasoning',
          parameter_count_b: 27.3,
          is_local: true,
          status: 'running',
          disk_path: '',
          disk_size_gb: 0,
          quantization: '',
          source: 'ollama',
        },
        {
          id: 'Qwen3.8-27B-UD-Q8_K_XL',
          name: 'Qwen3.8-27B-UD-Q8_K_XL',
          provider: 'unsloth',
          role: 'reasoning',
          parameter_count_b: 27.0,
          is_local: true,
          status: 'cached',
          disk_path: '/path/to/gguf',
          disk_size_gb: 29.3,
          quantization: 'UD-Q8_K_XL',
          source: 'huggingface_cache',
        },
        {
          id: 'Llama-3.2-1B-Instruct-4bit',
          name: 'Llama-3.2-1B-Instruct-4bit',
          provider: 'mlx',
          role: 'reasoning',
          parameter_count_b: 1.0,
          is_local: true,
          status: 'cached',
          disk_path: '/path/to/mlx',
          disk_size_gb: 0.7,
          quantization: '4bit',
          source: 'huggingface_cache',
        },
      ],
      message: '3 local models detected',
    });
  });

  it('renders model hub header, filter buttons, and dynamic local models', async () => {
    render(<ModelHubPage />);

    expect(screen.getByText('Model Hub')).toBeInTheDocument();
    expect(screen.getByText('UNSLOTH & LOCAL ECOSYSTEM')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
      expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
      expect(screen.getByText('Llama-3.2-1B-Instruct-4bit')).toBeInTheDocument();
    });
  });

  it('filters models when clicking category pills', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    });

    // Filter to Apple MLX
    const mlxBtn = screen.getByRole('button', { name: /Apple MLX/i });
    fireEvent.click(mlxBtn);

    expect(screen.getByText('Llama-3.2-1B-Instruct-4bit')).toBeInTheDocument();
    expect(screen.queryByText('qwen3.8:latest')).not.toBeInTheDocument();
    expect(screen.queryByText('Qwen3.8-27B-UD-Q8_K_XL')).not.toBeInTheDocument();
  });

  it('filters to balanced-or-better models when clicking the quant tier pill (running models exempt)', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    });

    // 균형 이상: balanced(4bit MLX) + premium(UD-Q8_K_XL) 표시.
    // running ollama(qwen3.8, unknown)는 등급 필터에서 면제되어 계속 표시 (Phase 42)
    fireEvent.click(screen.getByRole('button', { name: /균형 이상/i }));

    expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    expect(screen.getByText('Llama-3.2-1B-Instruct-4bit')).toBeInTheDocument();
    expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    // 필터 활성 시 표시 개수 안내 (running 모델 포함)
    expect(screen.getByText('3개 표시')).toBeInTheDocument();

    // 프리미엄만: premium + running 모델이 남음 (Llama balanced 제외)
    fireEvent.click(screen.getByRole('button', { name: /프리미엄만/i }));
    expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    expect(screen.queryByText('Llama-3.2-1B-Instruct-4bit')).not.toBeInTheDocument();
    expect(screen.getByText('2개 표시')).toBeInTheDocument();

    // 품질 전체로 복귀 → 모두 표시, 카운트 사라짐
    fireEvent.click(screen.getByRole('button', { name: /품질 전체/i }));
    expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    expect(screen.queryByText(/개 표시/)).not.toBeInTheDocument();
  });

  it('never hides a running model under any quant tier filter', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    });

    // 실행 중 모델(unknown 등급)은 등급 필터가 아무리 엄격해도 항상 표시
    for (const tier of [/균형 이상/i, /높음 이상/i, /프리미엄만/i]) {
      fireEvent.click(screen.getByRole('button', { name: tier }));
      expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    }
  });

  it('shows the empty-state notice when no model matches the quant tier filter', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    });

    // MLX 카테고리 + 프리미엄만 → 4bit MLX는 balanced라 제외 → MLX 프리미엄은 없음 → 빈 상태
    fireEvent.click(screen.getByRole('button', { name: /Apple MLX/i }));
    fireEvent.click(screen.getByRole('button', { name: /프리미엄만/i }));
    expect(screen.getByText('해당 조건에 맞는 로컬 모델을 찾을 수 없습니다.')).toBeInTheDocument();
  });

  it('shows quantization quality badges per quant level', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    });

    // UD-Q8_K_XL → premium(P), 4bit MLX → balanced(B), running Ollama(quant 없음) → unknown(?)
    const premium = screen.getByTitle('UD-Q8_K_XL — 프리미엄 — 원본 손실 거의 없음');
    expect(premium).toHaveClass('q-premium');
    expect(premium).toHaveTextContent('P');

    const balanced = screen.getByTitle('4bit — 균형 — 크기·품질 스위트스팟');
    expect(balanced).toHaveClass('q-balanced');
    expect(balanced).toHaveTextContent('B');

    const unknown = screen.getByTitle('Active — 양자화 정보 없음');
    expect(unknown).toHaveClass('q-unknown');
    expect(unknown).toHaveTextContent('?');
  });

  it('sorts models by disk size ascending and descending', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    });

    const select = screen.getByLabelText('정렬 기준');

    // 디스크 작은순: 0(running, 미보고) → 0.7 → 29.3
    fireEvent.change(select, { target: { value: 'disk-asc' } });
    let names = screen.getAllByText(/qwen3\.8:latest|Qwen3\.8-27B-UD-Q8_K_XL|Llama-3\.2-1B-Instruct-4bit/);
    expect(names.map((el) => el.textContent)).toEqual(['qwen3.8:latest', 'Llama-3.2-1B-Instruct-4bit', 'Qwen3.8-27B-UD-Q8_K_XL']);

    // 디스크 큰순: 29.3 → 0.7 → 0(running, 미보고)
    fireEvent.change(select, { target: { value: 'disk-desc' } });
    names = screen.getAllByText(/qwen3\.8:latest|Qwen3\.8-27B-UD-Q8_K_XL|Llama-3\.2-1B-Instruct-4bit/);
    expect(names.map((el) => el.textContent)).toEqual(['Qwen3.8-27B-UD-Q8_K_XL', 'Llama-3.2-1B-Instruct-4bit', 'qwen3.8:latest']);
  });

  it('sorts models by VRAM requirement descending', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    });

    // vramGb = params * 0.7: 27.0 → 19, 27.3(running) → 19, 1.0 → 1
    fireEvent.change(screen.getByLabelText('정렬 기준'), { target: { value: 'vram-desc' } });
    const names = screen.getAllByText(/qwen3\.8:latest|Qwen3\.8-27B-UD-Q8_K_XL|Llama-3\.2-1B-Instruct-4bit/);
    // 동률(19GB)은 stable sort로 원래 순서 유지 — Llama(1GB)가 마지막인지만 검증
    expect(names[names.length - 1].textContent).toBe('Llama-3.2-1B-Instruct-4bit');
  });

  it('filters models below the minimum disk size range', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    });

    const diskInput = screen.getByLabelText('최소 디스크 용량 (GB)');
    fireEvent.change(diskInput, { target: { value: '5' } });

    // 5GB 이상: UD-Q8_K_XL(29.3)만 — 미보고(0) 모델(running)은 제외되지 않음
    expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    expect(screen.queryByText('Llama-3.2-1B-Instruct-4bit')).not.toBeInTheDocument();
    expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();

    // 초기화 버튼으로 복원
    fireEvent.click(screen.getByRole('button', { name: /초기화/i }));
    expect(screen.getByText('Llama-3.2-1B-Instruct-4bit')).toBeInTheDocument();
  });

  it('filters models below the minimum VRAM range', async () => {
    render(<ModelHubPage />);

    await waitFor(() => {
      expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    });

    const vramInput = screen.getByLabelText('최소 VRAM 요구량 (GB)');
    fireEvent.change(vramInput, { target: { value: '10' } });

    // 10GB 이상: 27B 두 모델(~19GB)만 — Llama(~1GB) 제외
    expect(screen.getByText('Qwen3.8-27B-UD-Q8_K_XL')).toBeInTheDocument();
    expect(screen.getByText('qwen3.8:latest')).toBeInTheDocument();
    expect(screen.queryByText('Llama-3.2-1B-Instruct-4bit')).not.toBeInTheDocument();
  });
});
