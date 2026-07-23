/**
 * Output Store (Zustand)
 * =======================
 * Manages output logs from various sources: tool execution, build processes,
 * AI agent events, etc. Acts like VS Code's Output panel with source filtering.
 */
// @ts-nocheck
function stryNS_9fa48() {
  var g = typeof globalThis === 'object' && globalThis && globalThis.Math === Math && globalThis || new Function("return this")();
  var ns = g.__stryker__ || (g.__stryker__ = {});
  if (ns.activeMutant === undefined && g.process && g.process.env && g.process.env.__STRYKER_ACTIVE_MUTANT__) {
    ns.activeMutant = g.process.env.__STRYKER_ACTIVE_MUTANT__;
  }
  function retrieveNS() {
    return ns;
  }
  stryNS_9fa48 = retrieveNS;
  return retrieveNS();
}
stryNS_9fa48();
function stryCov_9fa48() {
  var ns = stryNS_9fa48();
  var cov = ns.mutantCoverage || (ns.mutantCoverage = {
    static: {},
    perTest: {}
  });
  function cover() {
    var c = cov.static;
    if (ns.currentTestId) {
      c = cov.perTest[ns.currentTestId] = cov.perTest[ns.currentTestId] || {};
    }
    var a = arguments;
    for (var i = 0; i < a.length; i++) {
      c[a[i]] = (c[a[i]] || 0) + 1;
    }
  }
  stryCov_9fa48 = cover;
  cover.apply(null, arguments);
}
function stryMutAct_9fa48(id) {
  var ns = stryNS_9fa48();
  function isActive(id) {
    if (ns.activeMutant === id) {
      if (ns.hitCount !== void 0 && ++ns.hitCount > ns.hitLimit) {
        throw new Error('Stryker: Hit count limit reached (' + ns.hitCount + ')');
      }
      return true;
    }
    return false;
  }
  stryMutAct_9fa48 = isActive;
  return isActive(id);
}
import { create } from 'zustand';
export type OutputLevel = 'info' | 'success' | 'warn' | 'error' | 'debug';
export const OUTPUT_SOURCES = {
  SYSTEM: 'System',
  TOOL: 'Tool',
  BUILD: 'Build',
  AGENT: 'Agent',
  TERMINAL: 'Terminal',
  GIT: 'Git'
} as const;
export type OutputSource = (typeof OUTPUT_SOURCES)[keyof typeof OUTPUT_SOURCES];
export interface OutputEntry {
  id: string;
  timestamp: string;
  source: OutputSource;
  level: OutputLevel;
  message: string;
  /** Optional structured data */
  data?: Record<string, any>;
}
export interface OutputState {
  entries: OutputEntry[];
  /** Active source filter (null = show all) */
  activeSource: OutputSource | null;
  /** Maximum entries to keep (ring buffer) */
  maxEntries: number;

  // Actions
  addOutput: (entry: Omit<OutputEntry, 'id' | 'timestamp'>) => void;
  clearOutput: () => void;
  setActiveSource: (source: OutputSource | null) => void;
}
let outputCounter = 0;
const MAX_ENTRIES = 5000;
export const useOutputStore = create<OutputState>(stryMutAct_9fa48("0") ? () => undefined : (stryCov_9fa48("0"), (set, get) => stryMutAct_9fa48("1") ? {} : (stryCov_9fa48("1"), {
  entries: stryMutAct_9fa48("2") ? ["Stryker was here"] : (stryCov_9fa48("2"), []),
  activeSource: null,
  maxEntries: MAX_ENTRIES,
  addOutput: entry => {
    if (stryMutAct_9fa48("3")) {
      {}
    } else {
      stryCov_9fa48("3");
      const id = stryMutAct_9fa48("4") ? `` : (stryCov_9fa48("4"), `out_${Date.now()}_${stryMutAct_9fa48("5") ? --outputCounter : (stryCov_9fa48("5"), ++outputCounter)}`);
      const newEntry: OutputEntry = stryMutAct_9fa48("6") ? {} : (stryCov_9fa48("6"), {
        ...entry,
        id,
        timestamp: new Date().toISOString()
      });
      set(state => {
        if (stryMutAct_9fa48("7")) {
          {}
        } else {
          stryCov_9fa48("7");
          const entries = stryMutAct_9fa48("8") ? [] : (stryCov_9fa48("8"), [...state.entries, newEntry]);
          // Ring buffer: trim oldest entries if over limit
          if (stryMutAct_9fa48("12") ? entries.length <= state.maxEntries : stryMutAct_9fa48("11") ? entries.length >= state.maxEntries : stryMutAct_9fa48("10") ? false : stryMutAct_9fa48("9") ? true : (stryCov_9fa48("9", "10", "11", "12"), entries.length > state.maxEntries)) {
            if (stryMutAct_9fa48("13")) {
              {}
            } else {
              stryCov_9fa48("13");
              return stryMutAct_9fa48("14") ? {} : (stryCov_9fa48("14"), {
                entries: stryMutAct_9fa48("15") ? entries : (stryCov_9fa48("15"), entries.slice(stryMutAct_9fa48("16") ? +state.maxEntries : (stryCov_9fa48("16"), -state.maxEntries)))
              });
            }
          }
          return stryMutAct_9fa48("17") ? {} : (stryCov_9fa48("17"), {
            entries
          });
        }
      });
    }
  },
  clearOutput: stryMutAct_9fa48("18") ? () => undefined : (stryCov_9fa48("18"), () => set(stryMutAct_9fa48("19") ? {} : (stryCov_9fa48("19"), {
    entries: stryMutAct_9fa48("20") ? ["Stryker was here"] : (stryCov_9fa48("20"), [])
  }))),
  setActiveSource: stryMutAct_9fa48("21") ? () => undefined : (stryCov_9fa48("21"), source => set(stryMutAct_9fa48("22") ? {} : (stryCov_9fa48("22"), {
    activeSource: source
  })))
})));

/* ─── Convenience helpers ──────────────────────────────────── */

export function logOutput(message: string, source: OutputSource = OUTPUT_SOURCES.SYSTEM, level: OutputLevel = stryMutAct_9fa48("23") ? "" : (stryCov_9fa48("23"), 'info'), data?: Record<string, any>) {
  if (stryMutAct_9fa48("24")) {
    {}
  } else {
    stryCov_9fa48("24");
    useOutputStore.getState().addOutput(stryMutAct_9fa48("25") ? {} : (stryCov_9fa48("25"), {
      source,
      level,
      message,
      data
    }));
  }
}
export function logToolOutput(message: string, data?: Record<string, any>) {
  if (stryMutAct_9fa48("26")) {
    {}
  } else {
    stryCov_9fa48("26");
    logOutput(message, OUTPUT_SOURCES.TOOL, stryMutAct_9fa48("27") ? "" : (stryCov_9fa48("27"), 'info'), data);
  }
}
export function logBuildOutput(message: string, level: OutputLevel = stryMutAct_9fa48("28") ? "" : (stryCov_9fa48("28"), 'info')) {
  if (stryMutAct_9fa48("29")) {
    {}
  } else {
    stryCov_9fa48("29");
    logOutput(message, OUTPUT_SOURCES.BUILD, level);
  }
}
export function logAgentOutput(message: string, level: OutputLevel = stryMutAct_9fa48("30") ? "" : (stryCov_9fa48("30"), 'info')) {
  if (stryMutAct_9fa48("31")) {
    {}
  } else {
    stryCov_9fa48("31");
    logOutput(message, OUTPUT_SOURCES.AGENT, level);
  }
}
export function logError(message: string, source: OutputSource = OUTPUT_SOURCES.SYSTEM) {
  if (stryMutAct_9fa48("32")) {
    {}
  } else {
    stryCov_9fa48("32");
    logOutput(message, source, stryMutAct_9fa48("33") ? "" : (stryCov_9fa48("33"), 'error'));
  }
}