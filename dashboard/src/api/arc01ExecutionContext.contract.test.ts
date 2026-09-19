import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  ConversationConflictPayloadSchema,
  ConversationSnapshotSchema,
  EXECUTION_CONTEXT_ERROR_HTTP_STATUS,
  ExecutionContextErrorCodeSchema,
  RequestExecutionContextSchema,
  RequestExecutionContextWireSchema,
} from './clientSchema';

const here = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(here, 'fixtures', 'arc01_request_execution_context.json');

type Arc01Fixture = {
  schema_version: number;
  wire_example: Record<string, unknown>;
  resolved_example: Record<string, unknown>;
  forbidden_authority_fields: string[];
  error_http_status: Record<string, number>;
  stale_conflict_example: Record<string, unknown>;
  conversation_snapshot_example: Record<string, unknown>;
};

function loadFixture(): Arc01Fixture {
  return JSON.parse(readFileSync(fixturePath, 'utf8')) as Arc01Fixture;
}

describe('ARC-01 RequestExecutionContext frozen contract', () => {
  it('parses wire and resolved examples from the shared fixture', () => {
    const fixture = loadFixture();
    const wire = RequestExecutionContextWireSchema.parse(fixture.wire_example);
    expect(wire.project_id).toBe('proj_arc01_alpha');
    expect(wire.client_hint_path).toBe('/tmp/client-hint-must-be-ignored');

    const resolved = RequestExecutionContextSchema.parse(fixture.resolved_example);
    expect(resolved.canonical_project_root).toContain('proj_arc01_alpha');
    expect(resolved.conversation_revision).toBe(3);
  });

  it('rejects raw path authority fields on the wire schema', () => {
    const fixture = loadFixture();
    for (const field of fixture.forbidden_authority_fields) {
      const payload = { ...fixture.wire_example, [field]: '/tmp/evil' };
      const result = RequestExecutionContextWireSchema.safeParse(payload);
      expect(result.success).toBe(false);
    }
  });

  it('aligns error HTTP status map with the shared fixture', () => {
    const fixture = loadFixture();
    expect(fixture.error_http_status).toEqual(EXECUTION_CONTEXT_ERROR_HTTP_STATUS);
    for (const code of Object.keys(fixture.error_http_status)) {
      expect(ExecutionContextErrorCodeSchema.parse(code)).toBe(code);
    }
  });

  it('parses stale conflict and conversation snapshot fixtures', () => {
    const fixture = loadFixture();
    const conflict = ConversationConflictPayloadSchema.parse(fixture.stale_conflict_example);
    expect(conflict.error).toBe('stale_conversation_revision');
    expect(conflict.current_revision).toBe(4);
    const snapshot = ConversationSnapshotSchema.parse(fixture.conversation_snapshot_example);
    expect(snapshot.revision).toBe(4);
    expect(snapshot.retained_message_ids).toEqual(['msg_1', 'msg_2']);
  });
});
