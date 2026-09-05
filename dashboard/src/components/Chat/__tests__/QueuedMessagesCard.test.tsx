import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueuedMessagesCard } from '../ChatActivity';

describe('QueuedMessagesCard Component', () => {
  const defaultProps = {
    items: ['첫 번째 대기 메시지', '두 번째 대기 메시지', '세 번째 대기 메시지'],
    collapsed: false,
    onToggleCollapse: vi.fn(),
    onSendNow: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onMoveUp: vi.fn(),
    onMoveDown: vi.fn(),
    onReorder: vi.fn(),
    onClearAll: vi.fn(),
  };

  it('renders nothing when items array is empty', () => {
    const { container } = render(<QueuedMessagesCard {...defaultProps} items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders queue header and item count correctly', () => {
    render(<QueuedMessagesCard {...defaultProps} />);
    expect(screen.getByText('Queued Messages')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Sends after agent finishes working')).toBeInTheDocument();
    expect(screen.getByText('첫 번째 대기 메시지')).toBeInTheDocument();
    expect(screen.getByText('두 번째 대기 메시지')).toBeInTheDocument();
    expect(screen.getByText('세 번째 대기 메시지')).toBeInTheDocument();
  });

  it('calls onMoveUp and onMoveDown when move buttons are clicked', () => {
    const onMoveUp = vi.fn();
    const onMoveDown = vi.fn();
    render(<QueuedMessagesCard {...defaultProps} onMoveUp={onMoveUp} onMoveDown={onMoveDown} />);

    const moveDownButtons = screen.getAllByRole('button', { name: '아래로 이동' });
    expect(moveDownButtons.length).toBeGreaterThan(0);
    fireEvent.click(moveDownButtons[0]);
    expect(onMoveDown).toHaveBeenCalledWith(0);

    const moveUpButtons = screen.getAllByRole('button', { name: '위로 이동' });
    expect(moveUpButtons.length).toBeGreaterThan(0);
    fireEvent.click(moveUpButtons[0]);
    // 두 번째 항목(index 1)의 위로 이동 버튼
    expect(onMoveUp).toHaveBeenCalledWith(1);
  });

  it('calls onClearAll when the clear all button is clicked', () => {
    const onClearAll = vi.fn();
    render(<QueuedMessagesCard {...defaultProps} onClearAll={onClearAll} />);

    const clearBtn = screen.getByText('대기열 모두 비우기');
    expect(clearBtn).toBeInTheDocument();
    fireEvent.click(clearBtn);
    expect(onClearAll).toHaveBeenCalledTimes(1);
  });

  it('supports drag and drop reordering', () => {
    const onReorder = vi.fn();
    const { container } = render(<QueuedMessagesCard {...defaultProps} onReorder={onReorder} />);

    const rows = container.querySelectorAll('.queued-row');
    expect(rows.length).toBe(3);

    // Drag row 0 and drop on row 2
    fireEvent.dragStart(rows[0], {
      dataTransfer: { setData: vi.fn(), getData: () => '0' },
    });
    fireEvent.dragOver(rows[2]);
    fireEvent.drop(rows[2], {
      dataTransfer: { getData: () => '0' },
    });

    expect(onReorder).toHaveBeenCalledWith(0, 2);
  });

  it('toggles collapse on header click', () => {
    const onToggleCollapse = vi.fn();
    render(<QueuedMessagesCard {...defaultProps} onToggleCollapse={onToggleCollapse} />);

    const header = screen.getByRole('button', { name: /Queued Messages/i });
    fireEvent.click(header);
    expect(onToggleCollapse).toHaveBeenCalledTimes(1);
  });
});
