import { describe, expect, it } from 'vitest';

import { parseSseChunk } from './taskExecutionApi';

describe('parseSseChunk', () => {
  it('parses complete frames, ignores keep-alives, and retains an incomplete frame', () => {
    const result = parseSseChunk(
      ': keep-alive\n\n' +
        'id: 7\nevent: tool.completed\ndata: {"sequence":7}\n\n' +
        'id: 8\nevent: task.completed\ndata: {"sequence":8',
    );

    expect(result.frames).toEqual([
      { id: '7', event: 'tool.completed', data: '{"sequence":7}' },
    ]);
    expect(result.remainder).toBe('id: 8\nevent: task.completed\ndata: {"sequence":8');
  });

  it('joins multi-line data fields according to the event-stream format', () => {
    const result = parseSseChunk('event: task.event\ndata: first\ndata: second\n\n');

    expect(result.frames[0]?.data).toBe('first\nsecond');
    expect(result.remainder).toBe('');
  });
});
