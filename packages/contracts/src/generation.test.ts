import { describe, expect, it } from 'vitest';
import { GenerationCandidateV1Schema, GenerationTaskV1Schema } from './generation';

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

  it('accepts imported candidates while they remain pending review', () => {
    const candidate = {
      candidate_id: '10000000-0000-4000-8000-000000000020',
      task_id: task.task_id,
      panel_id: task.panel_id,
      asset_id: '10000000-0000-4000-8000-000000000022',
      asset_version_id: '10000000-0000-4000-8000-000000000021',
      asset_name: '候选图片',
      asset_type: 'composite_panel',
      version_no: 1,
      mime: 'image/png',
      sha256: 'a'.repeat(64),
      byte_size: 100,
      width: 3,
      height: 2,
      status: 'pending_review',
      created_at: '2026-10-14T00:00:00Z',
      reviewed_at: null,
      reviewed_by_user_id: null,
      review_note: null,
    };
    expect(GenerationCandidateV1Schema.parse(candidate)).toEqual(candidate);
  });
});
