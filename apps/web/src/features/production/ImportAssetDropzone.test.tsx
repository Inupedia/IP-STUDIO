import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../lib/api';
import { ImportAssetDropzone } from './ImportAssetDropzone';

vi.mock('../../lib/api', () => ({
  api: {
    uploadAsset: vi.fn(),
    importGenerationCandidate: vi.fn(),
  },
}));

const panelId = '10000000-0000-4000-8000-000000000004';
const task = {
  task_id: '10000000-0000-4000-8000-000000000001',
  episode_id: '10000000-0000-4000-8000-000000000002',
  script_revision_id: '10000000-0000-4000-8000-000000000003',
  script_revision_no: 1,
  panel_id: panelId,
  mode: 'chatgpt_web' as const,
  status: 'waiting_manual_generation' as const,
  prompt_snapshot: { schema_version: '1.0' as const, text: '无字画格', panel: {}, locked_version_ids: [] },
  reference_snapshot: [],
  reference_bundle_url: '/references.zip',
  created_at: '2026-10-14T00:00:00Z',
};

const assetVersion = {
  asset_id: '10000000-0000-4000-8000-000000000010',
  asset_version_id: '10000000-0000-4000-8000-000000000011',
  workspace_id: '10000000-0000-4000-8000-000000000012',
  owner_ip_id: '10000000-0000-4000-8000-000000000013',
  type: 'composite_panel' as const,
  name: 'generated.png',
  status: 'candidate' as const,
  version_no: 1,
  sha256: 'a'.repeat(64),
  mime: 'image/png' as const,
  byte_size: 10,
  width: 2,
  height: 2,
  alpha: true,
  created_at: '2026-10-14T00:00:00Z',
};

const generationCandidate = {
  candidate_id: '10000000-0000-4000-8000-000000000020',
  task_id: task.task_id,
  panel_id: panelId,
  asset_version_id: assetVersion.asset_version_id,
  status: 'pending_review' as const,
  created_at: '2026-10-14T00:00:00Z',
};

function pasteImage(file: File) {
  const event = new Event('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(event, 'clipboardData', {
    value: {
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
    },
  });
  window.dispatchEvent(event);
}

describe('ImportAssetDropzone', () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.mocked(api.uploadAsset).mockReset();
    vi.mocked(api.importGenerationCandidate).mockReset();
  });

  it('routes clipboard image to the selected panel and binds it to its task', async () => {
    const image = new File([new Uint8Array([1, 2, 3])], 'generated.png', { type: 'image/png' });
    const onImported = vi.fn();
    vi.mocked(api.uploadAsset).mockResolvedValue(assetVersion);
    vi.mocked(api.importGenerationCandidate).mockResolvedValue(generationCandidate);
    render(
      <ImportAssetDropzone
        ipId={assetVersion.owner_ip_id}
        task={task}
        activePanelId={panelId}
        onImported={onImported}
      />,
    );

    pasteImage(image);

    await waitFor(() => expect(api.uploadAsset).toHaveBeenCalledWith(
      image,
      assetVersion.owner_ip_id,
      'generated',
      'composite_panel',
    ));
    await waitFor(() => expect(api.importGenerationCandidate).toHaveBeenCalledWith(
      task.task_id,
      assetVersion.asset_version_id,
    ));
    expect(onImported).toHaveBeenCalledWith(generationCandidate);
  });

  it('refuses clipboard images when no canvas panel is selected', async () => {
    const image = new File([new Uint8Array([1])], 'generated.png', { type: 'image/png' });
    render(
      <ImportAssetDropzone
        ipId={assetVersion.owner_ip_id}
        task={task}
        activePanelId={null}
        onImported={vi.fn()}
      />,
    );

    pasteImage(image);

    expect((await screen.findByRole('alert')).textContent).toContain('请先在画布中选择目标画格');
    expect(api.uploadAsset).not.toHaveBeenCalled();
    expect(api.importGenerationCandidate).not.toHaveBeenCalled();
  });

  it('does not upload an image when the selected panel differs from the task panel', async () => {
    const image = new File([new Uint8Array([1])], 'generated.png', { type: 'image/png' });
    render(
      <ImportAssetDropzone
        ipId={assetVersion.owner_ip_id}
        task={task}
        activePanelId="10000000-0000-4000-8000-000000000099"
        onImported={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('导入候选图片'), { target: { files: [image] } });

    expect((await screen.findByRole('alert')).textContent).toContain('此任务绑定的画格不是当前选中画格');
    expect(api.uploadAsset).not.toHaveBeenCalled();
  });

  it('imports a dropped image and reports clipboard permission denial', async () => {
    const image = new File([new Uint8Array([1, 2, 3])], 'dropped.png', { type: 'image/png' });
    vi.mocked(api.uploadAsset).mockResolvedValue(assetVersion);
    vi.mocked(api.importGenerationCandidate).mockResolvedValue(generationCandidate);
    render(
      <ImportAssetDropzone
        ipId={assetVersion.owner_ip_id}
        task={task}
        activePanelId={panelId}
        onImported={vi.fn()}
      />,
    );

    fireEvent.drop(screen.getByRole('group', { name: '拖入候选图片' }), {
      dataTransfer: { files: [image] },
    });
    await waitFor(() => expect(api.importGenerationCandidate).toHaveBeenCalledWith(
      task.task_id,
      assetVersion.asset_version_id,
    ));

    const read = vi.fn().mockRejectedValue(new DOMException('Blocked', 'NotAllowedError'));
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { read } });
    fireEvent.click(screen.getByRole('button', { name: '从剪贴板读取' }));

    expect((await screen.findByRole('alert')).textContent).toContain('浏览器拒绝读取剪贴板');
    expect(read).toHaveBeenCalledOnce();
  });
});
