import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../lib/api';
import { CodexStatus } from './CodexStatus';

vi.mock('../../lib/api', () => ({
  api: {
    getCodexCapabilities: vi.fn(),
    probeCodexCapabilities: vi.fn(),
    startCodexRun: vi.fn(),
    getCodexRun: vi.fn(),
    cancelCodexRun: vi.fn(),
  },
}));

const unavailable = {
  status: 'unavailable' as const,
  reason: '尚未通过本机 ImageGen 图片验证。',
  codex_path: null,
  codex_version: null,
  app_server_available: false,
  image_generation_advertised: false,
  e2e_verified: false,
  checked_at: '2026-10-14T00:00:00Z',
};

describe('CodexStatus', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('keeps native generation disabled until an explicit real image probe succeeds', async () => {
    vi.mocked(api.getCodexCapabilities).mockResolvedValue(unavailable);
    render(<CodexStatus taskId="task-1" />);

    expect(await screen.findByText(unavailable.reason)).toBeTruthy();
    expect(screen.queryByRole('button', { name: '使用 Codex 生成候选' })).toBeNull();
    expect(api.probeCodexCapabilities).not.toHaveBeenCalled();
  });

  it('requires an explicit probe before enabling a candidate run', async () => {
    const available = {
      ...unavailable,
      status: 'available' as const,
      reason: '本机 ImageGen 已通过图片验证。',
      codex_path: '/opt/codex',
      codex_version: 'codex-cli 0.162.1',
      app_server_available: true,
      image_generation_advertised: true,
      e2e_verified: true,
    };
    vi.mocked(api.getCodexCapabilities).mockResolvedValue(unavailable);
    vi.mocked(api.probeCodexCapabilities).mockResolvedValue(available);
    vi.mocked(api.startCodexRun).mockResolvedValue({
      run_id: 'run-1',
      task_id: 'task-1',
      panel_id: 'panel-1',
      status: 'candidate_ready',
      candidate_id: 'candidate-1',
      started_at: '2026-10-14T00:00:00Z',
      completed_at: '2026-10-14T00:00:02Z',
      error_reason: null,
      created_at: '2026-10-14T00:00:00Z',
    });
    render(<CodexStatus taskId="task-1" />);

    fireEvent.click(await screen.findByRole('button', { name: '验证本机 ImageGen 能力' }));
    expect(await screen.findByRole('button', { name: '使用 Codex 生成候选' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '使用 Codex 生成候选' }));
    await waitFor(() => expect(api.startCodexRun).toHaveBeenCalledWith('task-1'));
    expect(await screen.findByText(/候选已生成，等待人工审核/)).toBeTruthy();
  });

  it('offers a cancel action while a run is still queued or running', async () => {
    vi.mocked(api.getCodexCapabilities).mockResolvedValue({
      ...unavailable,
      status: 'available',
      reason: '已经验证',
      codex_path: '/opt/codex',
      codex_version: 'codex-cli 0.162.1',
      e2e_verified: true,
    });
    vi.mocked(api.startCodexRun).mockResolvedValue({
      run_id: '10000000-0000-4000-8000-000000000011',
      task_id: '10000000-0000-4000-8000-000000000012',
      panel_id: '10000000-0000-4000-8000-000000000013',
      status: 'running',
      candidate_id: null,
      started_at: '2026-10-14T00:00:00Z',
      completed_at: null,
      error_reason: null,
      created_at: '2026-10-14T00:00:00Z',
    });
    vi.mocked(api.cancelCodexRun).mockResolvedValue({
      run_id: '10000000-0000-4000-8000-000000000011',
      task_id: '10000000-0000-4000-8000-000000000012',
      panel_id: '10000000-0000-4000-8000-000000000013',
      status: 'failed',
      candidate_id: null,
      started_at: '2026-10-14T00:00:00Z',
      completed_at: '2026-10-14T00:00:01Z',
      error_reason: '已由管理员取消。',
      created_at: '2026-10-14T00:00:00Z',
    });
    render(<CodexStatus taskId="task-1" />);
    fireEvent.click(await screen.findByRole('button', { name: '使用 Codex 生成候选' }));
    fireEvent.click(await screen.findByRole('button', { name: '取消 Codex 生成' }));
    expect(api.cancelCodexRun).toHaveBeenCalledWith('10000000-0000-4000-8000-000000000011');
    expect(await screen.findByText(/已由管理员取消/)).toBeTruthy();
  });
});
