/** Shared types and helpers for Skills pages. */
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

export interface LocalSkill {
  name: string;
  path: string;
  source: 'market' | 'local';
  valid: boolean;
  has_skill_md: boolean;
  has_readme: boolean;
  version: string;
  tool_count: number;
  warnings: string[];
}

export interface PublishResult {
  success: boolean;
  action: 'npm_publish' | 'github_pr' | '';
  skill_name: string;
  package_name?: string;
  version?: string;
  npm_url?: string;
  pr_url?: string;
  errors: string[];
  warnings: string[];
  summary: string;
}

export interface PublishHistoryEntry {
  id: string;
  skill_name: string;
  action: 'npm_publish' | 'github_pr' | '';
  success: boolean;
  timestamp: string; // ISO 8601
  version?: string;
  package_name?: string;
  dry_run: boolean;
  summary: string;
  errors: string[];
  warnings: string[];
  npm_url?: string;
  pr_url?: string;
}

export function esc(str: string): string {
  return String(str || '').replace(/[&<>\"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] || c);
}
