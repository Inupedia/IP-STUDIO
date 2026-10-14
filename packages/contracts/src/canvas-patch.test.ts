import { describe, expect, it } from 'vitest';
import canvas from '../fixtures/canvas-v1.json';
import { CanvasPatchV1Schema, CodexPatchProposalV1Schema } from './canvas-patch';

const patch = {
  workspace_id: '10000000-0000-4000-8000-000000000001',
  ip_id: '10000000-0000-4000-8000-000000000002',
  episode_id: '10000000-0000-4000-8000-000000000003',
  document_id: '10000000-0000-4000-8000-000000000004',
  base_revision: 7,
  summary: '更新对白',
  operations: [{
    op: 'set_text',
    element_id: '10000000-0000-4000-8000-000000000005',
    text: '新的对白',
  }],
};

describe('CanvasPatchV1', () => {
  it('accepts only a scoped, versioned operation patch', () => {
    expect(CanvasPatchV1Schema.parse(patch)).toEqual(patch);
  });

  it('rejects unknown operations, extra command fields, and oversized patches', () => {
    expect(CanvasPatchV1Schema.safeParse({
      ...patch,
      operations: [{ op: 'run_command', command: 'rm -rf /' }],
    }).success).toBe(false);
    expect(CanvasPatchV1Schema.safeParse({
      ...patch,
      operations: [{ ...patch.operations[0], sql: 'UPDATE assets' }],
    }).success).toBe(false);
    expect(CanvasPatchV1Schema.safeParse({
      ...patch,
      operations: Array.from({ length: 51 }, () => patch.operations[0]),
    }).success).toBe(false);
  });

  it('accepts a persisted proposal with a full preview and pending approval state', () => {
    const proposal = {
      patch_id: '10000000-0000-4000-8000-000000000010',
      approval_id: '10000000-0000-4000-8000-000000000011',
      workspace_id: patch.workspace_id,
      ip_id: patch.ip_id,
      episode_id: patch.episode_id,
      document_id: patch.document_id,
      base_revision: patch.base_revision,
      patch,
      preview_document: canvas,
      status: 'pending_approval',
      created_by_user_id: '10000000-0000-4000-8000-000000000012',
      reviewed_by_user_id: null,
      reviewed_at: null,
      review_note: null,
      applied_revision: null,
      created_at: '2026-10-14T00:00:00Z',
    };
    expect(CodexPatchProposalV1Schema.safeParse(proposal).success).toBe(true);
  });
});
