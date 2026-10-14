import { describe, expect, it } from 'vitest';
import { GenerationTaskV1Schema } from './generation';

const task = {
  task_id: '10000000-0000-4000-8000-000000000001',
  episode_id: '10000000-0000-4000-8000-000000000002',
  script_revision_id: '10000000-0000-4000-8000-000000000003',
  script_revision_no: 1,
  panel_id: '10000000-0000-4000-8000-000000000004',
  mode: 'chatgpt_web',
  status: 'prepared',
  prompt_snapshot: {
    schema_version: '1.0',
    text: '生成单格插画，不要有文字。',
    panel: { panel_id: '10000000-0000-4000-8000-000000000004' },
    locked_version_ids: [],
  },
  reference_snapshot: [],
  reference_bundle_url: '/api/v1/generation-tasks/10000000-0000-4000-8000-000000000001/reference-bundle',
  created_at: '2026-10-14T00:00:00Z',
};

describe('GenerationTaskV1 contract', () => {
  it('accepts a frozen manual task snapshot', () => {
    expect(GenerationTaskV1Schema.parse(task)).toEqual(task);
  });

  it('rejects a task mode that has not been verified as available', () => {
    expect(() => GenerationTaskV1Schema.parse({ ...task, mode: 'codex_native' })).toThrow();
  });
});
