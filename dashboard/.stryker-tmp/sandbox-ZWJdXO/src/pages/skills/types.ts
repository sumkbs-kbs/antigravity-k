/** Shared types and helpers for Skills pages. */
// @ts-nocheck

export interface Skill {
  name?: string;
  id?: string;
  description?: string;
  source?: string;
  version?: string;
}

export interface MarketplaceSkill {
  name: string;
  skill_name?: string;
  version?: string;
  is_loaded?: boolean;
  mcp_server_id?: string;
}

export interface SearchResult {
  name: string;
  skill_name?: string;
  version: string;
  description?: string;
  keywords?: string[];
  publisher?: string;
}

export interface MCPServer {
  name?: string;
  server_name?: string;
  description?: string;
  status?: string;
  skill_name?: string;
  transport?: string;
  tools?: string[] | Array<{ name?: string; function?: { name?: string } }>;
  available_tools?: string[] | Array<{ name?: string; function?: { name?: string } }>;
}

export function esc(str: string): string {
  return String(str || '').replace(/[&<>\"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] || c);
}
