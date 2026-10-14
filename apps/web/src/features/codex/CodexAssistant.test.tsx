import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../lib/api';
import canvasFixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import type { CodexPatchProposalV1 } from '@ip-studio/contracts/canvas-patch';
import { CodexAssistant } from './CodexAssistant';

vi.mock('../../lib/api', () => ({
  api: {
    getCodexCapabilities: vi.fn(),
    getCodexPatchProposals: vi.fn(),
    proposeCodexPatch: vi.fn(),
    approveCodexPatch: vi.fn(),
    rejectCodexPatch: vi.fn(),
    getEpisodeDocument: vi.fn(),
  },
}));

describe('CodexAssistant', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('keeps a manual editing action visible when local Codex is unavailable', async () => {
    vi.mocked(api.getCodexCapabilities).mockResolvedValue({
      status: 'unavailable',
      reason: '当前没有可用的本机 Codex CLI。',
      codex_path: null,
      codex_version: null,
      app_server_available: false,
      image_generation_advertised: false,
      e2e_verified: false,
      checked_at: '2026-10-14T00:00:00Z',
    });
    vi.mocked(api.getCodexPatchProposals).mockResolvedValue([]);
    const onManualEdit = vi.fn();
    render(
      <CodexAssistant
        episodeId="10000000-0000-4000-8000-000000000002"
        currentRevision={1}
        currentDocument={null}
        onManualEdit={onManualEdit}
      />,
    );

    expect((await screen.findAllByText(/当前没有可用的本机 Codex CLI/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '继续手动编辑画布' })).toBeTruthy();
    expect(screen.getByText(/所有 Codex 修改都需要人工批准/)).toBeTruthy();
  });

  it('explains that unsupported ImageGen still allows read-only text suggestions', async () => {
    vi.mocked(api.getCodexCapabilities).mockResolvedValue({
      status: 'unsupported',
      reason: '当前 Codex 不支持 ImageGen。',
      codex_path: '/opt/codex',
      codex_version: 'codex-cli 0.162.1',
      app_server_available: true,
      image_generation_advertised: false,
      e2e_verified: false,
      checked_at: '2026-10-14T00:00:00Z',
    });
    vi.mocked(api.getCodexPatchProposals).mockResolvedValue([]);
    render(
      <CodexAssistant
        episodeId="10000000-0000-4000-8000-000000000002"
        currentRevision={1}
        currentDocument={null}
        onManualEdit={vi.fn()}
      />,
    );

    fireEvent.change(await screen.findByRole('textbox', { name: 'Codex 修改要求' }), {
      target: { value: '修改对白' },
    });
    expect(await screen.findByText(/只读文字建议/)).toBeTruthy();
    expect(screen.getByRole('button', { name: '生成 Patch 建议' }).hasAttribute('disabled')).toBe(false);
  });

  it('previews a patch and writes a new revision only after explicit approval', async () => {
    const currentDocument = structuredClone(canvasFixture) as unknown as CanvasDocumentV1;
    const previewDocument = structuredClone(currentDocument);
    const message = previewDocument.pages[0].panels[0].elements[1];
    if (message.type !== 'chat_message') throw new Error('Expected a chat message element');
    message.props.text = '候选对白';
    const proposal: CodexPatchProposalV1 = {
      patch_id: '10000000-0000-4000-8000-000000000010',
      approval_id: '10000000-0000-4000-8000-000000000011',
      workspace_id: '10000000-0000-4000-8000-000000000001',
      ip_id: '10000000-0000-4000-8000-000000000012',
      episode_id: currentDocument.episode_id,
      document_id: '10000000-0000-4000-8000-000000000013',
      base_revision: currentDocument.revision,
      patch: {
        workspace_id: '10000000-0000-4000-8000-000000000001',
        ip_id: '10000000-0000-4000-8000-000000000012',
        episode_id: currentDocument.episode_id,
        document_id: '10000000-0000-4000-8000-000000000013',
        base_revision: currentDocument.revision,
        summary: '更新朋友对白',
        operations: [{
          op: 'set_text',
          element_id: '00000000-0000-4000-8000-000000000010',
          text: '候选对白',
        }],
      },
      preview_document: previewDocument,
      status: 'pending_approval',
      created_by_user_id: '10000000-0000-4000-8000-000000000014',
      reviewed_by_user_id: null,
      reviewed_at: null,
      review_note: null,
      applied_revision: null,
      created_at: '2026-10-14T00:00:00Z',
    };
    const reviewed = {
      ...proposal,
      status: 'approved' as const,
      reviewed_by_user_id: '10000000-0000-4000-8000-000000000014',
      reviewed_at: '2026-10-14T00:00:02Z',
      applied_revision: currentDocument.revision + 1,
    };
    vi.mocked(api.getCodexCapabilities).mockResolvedValue({
      status: 'available',
      reason: '本机 Codex 可用',
      codex_path: '/opt/codex',
      codex_version: 'codex-cli 0.162.1',
      app_server_available: true,
      image_generation_advertised: true,
      e2e_verified: true,
      checked_at: '2026-10-14T00:00:00Z',
    });
    vi.mocked(api.getCodexPatchProposals).mockResolvedValue([]);
    vi.mocked(api.proposeCodexPatch).mockResolvedValue(proposal);
    vi.mocked(api.approveCodexPatch).mockResolvedValue(reviewed);
    vi.mocked(api.getEpisodeDocument).mockResolvedValue({
      revision: currentDocument.revision + 1,
      document: previewDocument,
    });
    const onApplied = vi.fn();
    render(
      <CodexAssistant
        episodeId={currentDocument.episode_id}
        currentRevision={currentDocument.revision}
        currentDocument={currentDocument}
        onApplied={onApplied}
        onManualEdit={vi.fn()}
      />,
    );

    fireEvent.change(await screen.findByRole('textbox', { name: 'Codex 修改要求' }), {
      target: { value: '更新朋友对白' },
    });
    fireEvent.click(screen.getByRole('button', { name: '生成 Patch 建议' }));
    expect(await screen.findByText(/在吗？ → 候选对白/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '批准并写入 revision 6' }));

    await waitFor(() => expect(api.approveCodexPatch).toHaveBeenCalledWith(
      proposal.patch_id,
      proposal.base_revision,
      proposal.approval_id,
    ));
    await waitFor(() => expect(onApplied).toHaveBeenCalledWith(previewDocument));
  });
});
