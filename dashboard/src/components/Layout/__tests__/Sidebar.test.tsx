import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '../Sidebar';

describe('Sidebar Ssak-Ai Desktop layout', () => {
  it('renders Ssak-Ai header, 5 primary navigation rows, real projects with add button, and user profile', () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    expect(screen.getAllByText('Ssak-Ai').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('새 채팅')).toBeInTheDocument();
    expect(screen.getByText('풀 리퀘스트')).toBeInTheDocument();
    expect(screen.getByText('예약')).toBeInTheDocument();
    expect(screen.getByText('플러그인')).toBeInTheDocument();
    expect(screen.getByText('탐색')).toBeInTheDocument();
    expect(screen.getByText('프로젝트')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /새 프로젝트 추가/i })).toBeInTheDocument();
    expect(screen.queryByText(/사용량.*남음/i)).toBeNull();
    expect(screen.getByText(/mr\.k/i)).toBeInTheDocument();
    expect(screen.getByText('음성')).toBeInTheDocument();
  });
});
