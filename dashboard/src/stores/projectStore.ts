/**
 * Project Store (Zustand) — WS-04 single source of truth
 * ======================================================
 * Active project id / name / path / session binding revision and a
 * monotonic switchEpoch for cancelling / isolating in-flight requests.
 */

import { create } from 'zustand';
import {
  ProjectListResponseSchema,
  type ProjectRecord,
} from '../api/clientSchema';
import {
  SESSION_ID_HEADER,
  getOrCreateClientSessionId,
} from '../api/clientSession';
import { createAccessPinHeaders } from '../utils/accessPinCredential';

const ACTIVE_PROJECT_PATH_KEY = 'agk_active_project';
const ACTIVE_PROJECT_ID_KEY = 'agk_active_project_id';

export type ProjectSwitchResult = Readonly<{
  ok: boolean;
  project?: ProjectRecord;
  revision?: number;
  detail?: string;
}>;

export interface ProjectState {
  projects: ProjectRecord[];
  activeProjectId: string | null;
  activeProjectName: string;
  activeProjectPath: string;
  /** Session active-project binding revision from the server (when known). */
  projectRevision: number | null;
  /** Monotonic client generation bumped on every successful identity change. */
  switchEpoch: number;
  isSwitching: boolean;
  lastSwitchError: string | null;
  hydrated: boolean;

  setProjects: (projects: ProjectRecord[]) => void;
  applyActiveProject: (
    project: Pick<ProjectRecord, 'id' | 'name' | 'path'> & Partial<ProjectRecord>,
    revision?: number | null,
  ) => void;
  hydrateFromServer: () => Promise<void>;
  switchToProject: (proj: ProjectRecord) => Promise<ProjectSwitchResult>;
  registerAndSwitch: (path: string, name: string) => Promise<ProjectSwitchResult>;
  removeProject: (proj: ProjectRecord) => Promise<ProjectSwitchResult>;
  getIdentity: () => {
    projectId: string | null;
    projectRevision: number | null;
    switchEpoch: number;
    sessionId: string;
    projectName: string;
    projectPath: string;
  };
}

function sessionHeaders(extra?: HeadersInit): Headers {
  const headers = createAccessPinHeaders(extra);
  headers.set(SESSION_ID_HEADER, getOrCreateClientSessionId());
  return headers;
}

function markActive(projects: ProjectRecord[], activeId: string | null): ProjectRecord[] {
  if (!activeId) return projects;
  return projects.map((p) => ({ ...p, is_active: p.id === activeId }));
}

function persistActive(project: { id: string; path: string }): void {
  try {
    localStorage.setItem(ACTIVE_PROJECT_PATH_KEY, project.path);
    localStorage.setItem(ACTIVE_PROJECT_ID_KEY, project.id);
  } catch {
    /* ignore quota / private mode */
  }
}

function readPersistedPath(): string {
  try {
    return localStorage.getItem(ACTIVE_PROJECT_PATH_KEY) || '/';
  } catch {
    return '/';
  }
}

function extractRevision(raw: unknown): number | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const binding = (raw as { session_active_project?: unknown }).session_active_project;
  if (typeof binding !== 'object' || binding === null) return null;
  const rev = (binding as { revision?: unknown }).revision;
  return typeof rev === 'number' && Number.isFinite(rev) ? rev : null;
}

function extractProject(raw: unknown): ProjectRecord | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const project = (raw as { project?: unknown }).project;
  if (typeof project !== 'object' || project === null) return null;
  const p = project as Record<string, unknown>;
  if (typeof p.id !== 'string' || typeof p.name !== 'string') return null;
  return {
    id: p.id,
    name: p.name,
    path: typeof p.path === 'string' ? p.path : '',
    is_active: true,
    tasks: Array.isArray(p.tasks) ? p.tasks.filter((t): t is string => typeof t === 'string') : [],
    last_accessed_at: typeof p.last_accessed_at === 'string' ? p.last_accessed_at : undefined,
    preview: typeof p.preview === 'string' ? p.preview : undefined,
  };
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProjectId: null,
  activeProjectName: 'Ssak-Ai',
  activeProjectPath: readPersistedPath(),
  projectRevision: null,
  switchEpoch: 0,
  isSwitching: false,
  lastSwitchError: null,
  hydrated: false,

  setProjects: (projects) => {
    const { activeProjectId } = get();
    set({ projects: markActive(projects, activeProjectId) });
  },

  applyActiveProject: (project, revision = null) => {
    const nextRev =
      revision != null && Number.isFinite(revision) ? revision : get().projectRevision;
    persistActive({ id: project.id, path: project.path });
    set((state) => ({
      activeProjectId: project.id,
      activeProjectName: project.name,
      activeProjectPath: project.path,
      projectRevision: nextRev,
      switchEpoch: state.switchEpoch + 1,
      lastSwitchError: null,
      projects: markActive(
        state.projects.some((p) => p.id === project.id)
          ? state.projects
          : [...state.projects, { ...project, is_active: true, tasks: project.tasks ?? [] }],
        project.id,
      ),
    }));
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('agk:project-switched', {
          detail: {
            projectId: project.id,
            projectName: project.name,
            projectPath: project.path,
            projectRevision: nextRev,
            switchEpoch: get().switchEpoch,
          },
        }),
      );
      window.dispatchEvent(new CustomEvent('agk:projects-changed'));
    }
  },

  hydrateFromServer: async () => {
    try {
      const res = await fetch('/api/projects', { headers: sessionHeaders() });
      if (!res.ok) {
        set({ hydrated: true });
        return;
      }
      const raw: unknown = await res.json();
      const parsed = ProjectListResponseSchema.safeParse(raw);
      if (!parsed.success) {
        set({ hydrated: true });
        return;
      }
      const list = parsed.data.projects;
      const current =
        parsed.data.current_project
        || list.find((p) => p.is_active)
        || list[0]
        || null;
      if (current) {
        persistActive({ id: current.id, path: current.path });
        set((state) => ({
          projects: markActive(list, current.id),
          activeProjectId: current.id,
          activeProjectName: current.name,
          activeProjectPath: current.path,
          // Do not bump epoch on initial hydrate — avoids aborting first paint.
          projectRevision: state.projectRevision,
          hydrated: true,
          lastSwitchError: null,
        }));
      } else {
        set({ projects: list, hydrated: true });
      }
    } catch {
      set({ hydrated: true });
    }
  },

  switchToProject: async (proj) => {
    set({ isSwitching: true, lastSwitchError: null });
    try {
      const res = await fetch('/api/projects/switch', {
        method: 'POST',
        headers: sessionHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ project_id: proj.id }),
      });
      const raw: unknown = await res.json().catch(() => null);
      if (!res.ok) {
        const detail =
          typeof raw === 'object' && raw && 'detail' in raw && typeof (raw as { detail: unknown }).detail === 'string'
            ? (raw as { detail: string }).detail
            : `HTTP ${res.status}`;
        set({ isSwitching: false, lastSwitchError: detail });
        return { ok: false, detail };
      }
      const project = extractProject(raw) ?? { ...proj, is_active: true };
      const revision = extractRevision(raw);
      get().applyActiveProject(project, revision);
      set({ isSwitching: false });
      return { ok: true, project, revision: revision ?? undefined };
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      set({ isSwitching: false, lastSwitchError: detail });
      return { ok: false, detail };
    }
  },

  registerAndSwitch: async (path, name) => {
    set({ isSwitching: true, lastSwitchError: null });
    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: sessionHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ path, name }),
      });
      const raw: unknown = await res.json().catch(() => null);
      if (!res.ok) {
        const detail =
          typeof raw === 'object' && raw && 'detail' in raw && typeof (raw as { detail: unknown }).detail === 'string'
            ? (raw as { detail: string }).detail
            : `HTTP ${res.status}`;
        set({ isSwitching: false, lastSwitchError: detail });
        return { ok: false, detail };
      }
      const project = extractProject(raw);
      if (!project) {
        const detail = 'Project registration response missing project';
        set({ isSwitching: false, lastSwitchError: detail });
        return { ok: false, detail };
      }
      const revision = extractRevision(raw);
      get().applyActiveProject(project, revision);
      set({ isSwitching: false });
      return { ok: true, project, revision: revision ?? undefined };
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      set({ isSwitching: false, lastSwitchError: detail });
      return { ok: false, detail };
    }
  },

  removeProject: async (proj) => {
    set({ isSwitching: true, lastSwitchError: null });
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(proj.id)}`, {
        method: 'DELETE',
        headers: sessionHeaders(),
      });
      if (!res.ok) {
        const detail = `HTTP ${res.status}`;
        set({ isSwitching: false, lastSwitchError: detail });
        return { ok: false, detail };
      }
      await get().hydrateFromServer();
      const { activeProjectId, activeProjectName, activeProjectPath, projectRevision } = get();
      if (activeProjectId) {
        // hydrate does not bump epoch; force isolation after delete-of-active.
        if (proj.is_active || proj.id === activeProjectId) {
          get().applyActiveProject(
            { id: activeProjectId, name: activeProjectName, path: activeProjectPath },
            projectRevision,
          );
        }
      }
      set({ isSwitching: false });
      return { ok: true };
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      set({ isSwitching: false, lastSwitchError: detail });
      return { ok: false, detail };
    }
  },

  getIdentity: () => {
    const s = get();
    return {
      projectId: s.activeProjectId,
      projectRevision: s.projectRevision,
      switchEpoch: s.switchEpoch,
      sessionId: getOrCreateClientSessionId(),
      projectName: s.activeProjectName,
      projectPath: s.activeProjectPath,
    };
  },
}));
