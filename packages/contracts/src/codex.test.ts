import { describe, expect, it } from 'vitest';
import { CodexCapabilityV1Schema, CodexRunV1Schema } from './codex';

const run = {
  run_id: '10000000-0000-4000-8000-000000000001',
  task_id: '10000000-0000-4000-8000-000000000002',
  panel_id: '10000000-0000-4000-8000-000000000003',
  status: 'candidate_ready',
  candidate_id: '10000000-0000-4000-8000-000000000004',
  started_at: '2026-10-14T00:00:00Z',
  completed_at: '2026-10-14T00:00:02Z',
  error_reason: null,
  created_at: '2026-10-14T00:00:00Z',
};

describe('Codex integration contracts', () => {
  it('accepts a capability report with explicit E2E verification state', () => {
    const report = {
      status: 'available',
      reason: '已通过真实图片验证',
      codex_path: '/opt/codex',
      codex_version: 'codex-cli 0.162.1',
      app_server_available: true,
      image_generation_advertised: true,
      e2e_verified: true,
      checked_at: '2026-10-14T00:00:00Z',
    };
    expect(CodexCapabilityV1Schema.parse(report)).toEqual(report);
  });

  it('requires a candidate reference for a candidate-ready run', () => {
    expect(CodexRunV1Schema.parse(run)).toEqual(run);
    expect(() => CodexRunV1Schema.parse({ ...run, candidate_id: null })).toThrow();
  });
});
