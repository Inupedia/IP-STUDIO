import { describe, expect, it } from 'vitest';
import { CanvasPatchV1Schema } from './canvas-patch';

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
});
