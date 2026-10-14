import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { GenerationTaskV1 } from '@ip-studio/contracts/generation';
import { GenerationTaskCard } from './GenerationTaskCard';

const task: GenerationTaskV1 = {
  task_id: '10000000-0000-4000-8000-000000000001',
  episode_id: '10000000-0000-4000-8000-000000000002',
  script_revision_id: '10000000-0000-4000-8000-000000000003',
  script_revision_no: 1,
  panel_id: '10000000-0000-4000-8000-000000000004',
  mode: 'chatgpt_web',
  status: 'prepared',
  prompt_snapshot: {
    schema_version: '1.0',
    text: '生成一张无字漫画单格。',
    panel: { panel_id: '10000000-0000-4000-8000-000000000004' },
    locked_version_ids: ['10000000-0000-4000-8000-000000000005'],
  },
  reference_snapshot: [{
    kind: 'character_version',
    version_id: '10000000-0000-4000-8000-000000000005',
    entity_id: '10000000-0000-4000-8000-000000000006',
    version_no: 1,
    name: '卡仔',
    bible: {},
    bible_summary: '圆脸',
  }],
  reference_bundle_url: '/api/v1/generation-tasks/10000000-0000-4000-8000-000000000001/reference-bundle',
  created_at: '2026-10-14T00:00:00Z',
};

describe('GenerationTaskCard', () => {
  afterEach(cleanup);

  it('copies the frozen prompt and exposes the exact reference versions', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const download = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    render(
      <GenerationTaskCard
        task={task}
        onStartManualGeneration={vi.fn()}
        onDownloadReferenceBundle={download}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '复制提示词' }));

    expect(await screen.findByText('提示词已复制')).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith(task.prompt_snapshot.text);
    expect(screen.getByText(/CharacterVersion|卡仔/).textContent).toContain('卡仔');
    expect(screen.getByDisplayValue(task.prompt_snapshot.text)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '下载参考包 ZIP' }));
    expect(await screen.findByText('参考包已下载')).toBeTruthy();
    expect(download).toHaveBeenCalledOnce();
  });

  it('starts the manual task only after the operator confirms the external handoff', async () => {
    const startManual = vi.fn().mockResolvedValue(undefined);
    render(
      <GenerationTaskCard
        task={task}
        onStartManualGeneration={startManual}
        onDownloadReferenceBundle={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '我已在 ChatGPT Web 开始生成' }));

    expect(startManual).toHaveBeenCalledOnce();
    expect(await screen.findByText('人工生成中')).toBeTruthy();
  });
});
