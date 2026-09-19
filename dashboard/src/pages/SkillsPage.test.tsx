import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import SkillsPage from './SkillsPage';

describe('SkillsPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads the all-skills tab through a checked JSON request', async () => {
    const json = vi.fn().mockResolvedValue({ skills: [{ id: 'skill-1', name: 'Demo Skill', source: 'local' }] });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json }));

    render(<SkillsPage />);

    await waitFor(() => expect(screen.getByText('Demo Skill')).toBeInTheDocument());
    expect(fetch).toHaveBeenCalledWith('/api/system/skills', undefined);
    expect(json).toHaveBeenCalledTimes(1);
  });

  it('does not parse a failed all-skills response', async () => {
    const json = vi.fn().mockResolvedValue({ detail: 'unavailable' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json }));
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<SkillsPage />);

    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/system/skills', undefined));
    expect(json).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalled();
    expect(screen.getByText(/로드된 스킬이 없습니다/)).toBeInTheDocument();
  });
});
