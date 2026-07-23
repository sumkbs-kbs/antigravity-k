/**
 * terminalStore Tests
 * ====================
 * Tests for the Zustand terminal store — session CRUD, visibility, rename.
 * Phase 6 (Multi-Terminal) core functionality.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useTerminalStore, generateTerminalId } from '../terminalStore';

beforeEach(() => {
  useTerminalStore.setState({
    sessions: [],
    activeSessionId: null,
    visible: false,
  });
});

describe('generateTerminalId', () => {
  it('generates a string starting with term_', () => {
    const id = generateTerminalId();
    expect(id).toMatch(/^term_/);
  });

  it('generates unique IDs', () => {
    const ids = new Set(Array.from({ length: 100 }, () => generateTerminalId()));
    expect(ids.size).toBe(100);
  });

  it('generates IDs with exactly 4-char suffix after second underscore', () => {
    for (let i = 0; i < 50; i++) {
      const id = generateTerminalId();
      expect(id).toMatch(/^term_\d+_[a-z0-9]{4}$/);
    }
  });
});

describe('useTerminalStore', () => {
  /* ─── Initial State ─────────────────────────────────────── */

  it('starts with no sessions and hidden', () => {
    const state = useTerminalStore.getState();
    expect(state.sessions).toHaveLength(0);
    expect(state.activeSessionId).toBeNull();
    expect(state.visible).toBe(false);
  });

  /* ─── addSession ───────────────────────────────────────── */

  it('adds a session with auto-generated name', () => {
    const id = useTerminalStore.getState().addSession();

    const state = useTerminalStore.getState();
    expect(state.sessions).toHaveLength(1);
    expect(state.sessions[0].id).toBe(id);
    expect(state.sessions[0].name).toMatch(/^Terminal \d+$/);
    expect(state.sessions[0].createdAt).toBeDefined();
    expect(state.activeSessionId).toBe(id);
    expect(state.visible).toBe(true);
  });

  it('adds a session with custom name', () => {
    const id = useTerminalStore.getState().addSession('My Custom Terminal');

    const session = useTerminalStore.getState().sessions[0];
    expect(session.name).toBe('My Custom Terminal');
  });

  it('uses default counter name when name is empty string', () => {
    useTerminalStore.getState().addSession('');

    const session = useTerminalStore.getState().sessions[0];
    expect(session.name).toMatch(/^Terminal \d+$/);
    expect(session.name).not.toBe('');
  });

  it('increments terminal counter across sequential calls', () => {
    const id1 = useTerminalStore.getState().addSession();
    const id2 = useTerminalStore.getState().addSession();
    const id3 = useTerminalStore.getState().addSession();

    const sessions = useTerminalStore.getState().sessions;
    expect(sessions).toHaveLength(3);
    expect(sessions[0].name).toMatch(/^Terminal \d+$/);
    expect(sessions[1].name).toMatch(/^Terminal \d+$/);
    expect(sessions[2].name).toMatch(/^Terminal \d+$/);
    // All names should be different (counter incremented)
    expect(sessions[0].name).not.toBe(sessions[1].name);
    expect(sessions[1].name).not.toBe(sessions[2].name);
  });

  it('auto-activates the newly added session', () => {
    useTerminalStore.getState().addSession('First');
    const firstId = useTerminalStore.getState().activeSessionId;

    const secondId = useTerminalStore.getState().addSession('Second');
    expect(useTerminalStore.getState().activeSessionId).toBe(secondId);
    expect(useTerminalStore.getState().activeSessionId).not.toBe(firstId);
  });

  it('returns the new session ID', () => {
    const id = useTerminalStore.getState().addSession();
    expect(typeof id).toBe('string');
    expect(id).toMatch(/^term_/);
  });

  /* ─── closeSession ──────────────────────────────────────── */

  it('removes the session from the list', () => {
    const id = useTerminalStore.getState().addSession();
    useTerminalStore.getState().closeSession(id);

    expect(useTerminalStore.getState().sessions).toHaveLength(0);
  });

  it('switches to another session when closing the active one', () => {
    useTerminalStore.getState().addSession('First');
    const firstId = useTerminalStore.getState().activeSessionId!;
    const secondId = useTerminalStore.getState().addSession('Second');

    useTerminalStore.getState().closeSession(firstId);

    expect(useTerminalStore.getState().activeSessionId).toBe(secondId);
    expect(useTerminalStore.getState().sessions).toHaveLength(1);
  });

  it('sets activeSessionId to null when closing the last session', () => {
    const id = useTerminalStore.getState().addSession();
    useTerminalStore.getState().closeSession(id);

    expect(useTerminalStore.getState().activeSessionId).toBeNull();
  });

  it('hides terminal panel when all sessions are closed', () => {
    const id = useTerminalStore.getState().addSession();
    useTerminalStore.getState().closeSession(id);

    expect(useTerminalStore.getState().visible).toBe(false);
  });

  it('does nothing when closing a non-existent session', () => {
    useTerminalStore.getState().addSession('First');
    useTerminalStore.getState().closeSession('nonexistent-id');

    expect(useTerminalStore.getState().sessions).toHaveLength(1);
  });

  it('does not change activeSessionId when closing a non-active session', () => {
    const id1 = useTerminalStore.getState().addSession('First');
    useTerminalStore.getState().addSession('Second');
    // Active is Second (last added)

    useTerminalStore.getState().closeSession(id1);

    expect(useTerminalStore.getState().activeSessionId).not.toBeNull();
    expect(useTerminalStore.getState().sessions).toHaveLength(1);
  });

  it('keeps activeSessionId exactly the same when closing non-active session that is last in array', () => {
    // Setup: 3 sessions, set active to first, close last (non-active)
    const idA = useTerminalStore.getState().addSession('A');
    useTerminalStore.getState().addSession('B');
    const idC = useTerminalStore.getState().addSession('C');
    // A is first, C is active (last added)

    // Switch active to A
    useTerminalStore.getState().setActiveSession(idA);
    expect(useTerminalStore.getState().activeSessionId).toBe(idA);

    // Close C (non-active, but last in array — would be picked by remaining[last])
    useTerminalStore.getState().closeSession(idC);

    // activeSessionId must remain A (not switch to B which is remaining[last-1])
    expect(useTerminalStore.getState().activeSessionId).toBe(idA);
    expect(useTerminalStore.getState().sessions).toHaveLength(2);
  });

  it('switches active session when closing the actual active session with remaining', () => {
    const idA = useTerminalStore.getState().addSession('A');
    const idB = useTerminalStore.getState().addSession('B');
    // B is active (last added)

    // Close B (active session)
    useTerminalStore.getState().closeSession(idB);

    // Should switch to A, not null
    expect(useTerminalStore.getState().activeSessionId).toBe(idA);
    expect(useTerminalStore.getState().activeSessionId).not.toBeNull();
    expect(useTerminalStore.getState().sessions).toHaveLength(1);
  });

  it('keeps terminal panel visible when closing a session with remaining sessions', () => {
    useTerminalStore.getState().addSession('A');
    const idB = useTerminalStore.getState().addSession('B');

    useTerminalStore.getState().closeSession(idB);

    // Visible should remain true because there are still sessions
    expect(useTerminalStore.getState().visible).toBe(true);
    expect(useTerminalStore.getState().sessions).toHaveLength(1);
  });

  it('keeps remaining sessions after closing one', () => {
    useTerminalStore.getState().addSession('A');
    const idB = useTerminalStore.getState().addSession('B');
    useTerminalStore.getState().addSession('C');

    useTerminalStore.getState().closeSession(idB);

    const sessions = useTerminalStore.getState().sessions;
    expect(sessions).toHaveLength(2);
    expect(sessions[0].name).toBe('A');
    expect(sessions[1].name).toBe('C');
  });

  /* ─── setActiveSession ──────────────────────────────────── */

  it('sets the active session and makes panel visible', () => {
    const id1 = useTerminalStore.getState().addSession('First');
    const id2 = useTerminalStore.getState().addSession('Second');

    useTerminalStore.getState().setActiveSession(id1);

    expect(useTerminalStore.getState().activeSessionId).toBe(id1);
    expect(useTerminalStore.getState().visible).toBe(true);
  });

  /* ─── renameSession ─────────────────────────────────────── */

  it('renames a session', () => {
    const id = useTerminalStore.getState().addSession('Old Name');
    useTerminalStore.getState().renameSession(id, 'New Name');

    const session = useTerminalStore.getState().sessions[0];
    expect(session.name).toBe('New Name');
  });

  it('only renames the target session', () => {
    const id1 = useTerminalStore.getState().addSession('First');
    useTerminalStore.getState().addSession('Second');

    useTerminalStore.getState().renameSession(id1, 'Renamed First');

    const sessions = useTerminalStore.getState().sessions;
    expect(sessions[0].name).toBe('Renamed First');
    expect(sessions[1].name).toBe('Second');
  });

  it('does nothing when renaming a non-existent session', () => {
    useTerminalStore.getState().addSession('First');
    useTerminalStore.getState().renameSession('nonexistent', 'Should Not Appear');

    const sessions = useTerminalStore.getState().sessions;
    expect(sessions).toHaveLength(1);
    expect(sessions[0].name).toBe('First');
  });

  it('renames session from middle of list correctly', () => {
    const id1 = useTerminalStore.getState().addSession('A');
    const id2 = useTerminalStore.getState().addSession('B');
    const id3 = useTerminalStore.getState().addSession('C');

    useTerminalStore.getState().renameSession(id2, 'B-Renamed');

    const sessions = useTerminalStore.getState().sessions;
    expect(sessions[0].name).toBe('A');
    expect(sessions[1].name).toBe('B-Renamed');
    expect(sessions[2].name).toBe('C');
  });

  /* ─── setVisible / toggleVisible ────────────────────────── */

  it('setVisible shows/hides the panel', () => {
    useTerminalStore.getState().setVisible(true);
    expect(useTerminalStore.getState().visible).toBe(true);

    useTerminalStore.getState().setVisible(false);
    expect(useTerminalStore.getState().visible).toBe(false);
  });

  it('toggleVisible adds a session when none exist and panel is hidden', () => {
    expect(useTerminalStore.getState().sessions).toHaveLength(0);

    useTerminalStore.getState().toggleVisible();

    const state = useTerminalStore.getState();
    expect(state.sessions).toHaveLength(1);
    expect(state.visible).toBe(true);
  });

  it('toggleVisible toggles panel when sessions exist', () => {
    useTerminalStore.getState().addSession();
    useTerminalStore.getState().setVisible(false);

    useTerminalStore.getState().toggleVisible();
    expect(useTerminalStore.getState().visible).toBe(true);

    useTerminalStore.getState().toggleVisible();
    expect(useTerminalStore.getState().visible).toBe(false);
  });

  it('toggleVisible does not add extra session when sessions exist and panel is hidden', () => {
    useTerminalStore.getState().addSession();
    expect(useTerminalStore.getState().sessions).toHaveLength(1);
    useTerminalStore.getState().setVisible(false);

    useTerminalStore.getState().toggleVisible();

    // Should NOT add a new session — only toggle visibility
    expect(useTerminalStore.getState().sessions).toHaveLength(1);
    expect(useTerminalStore.getState().visible).toBe(true);
  });

  it('toggleVisible does not add session when panel is already visible', () => {
    useTerminalStore.getState().addSession();
    useTerminalStore.getState().setVisible(true);

    useTerminalStore.getState().toggleVisible();

    // Should NOT add a new session (panel is visible, just toggle)
    expect(useTerminalStore.getState().sessions).toHaveLength(1);
    expect(useTerminalStore.getState().visible).toBe(false);
  });
});
