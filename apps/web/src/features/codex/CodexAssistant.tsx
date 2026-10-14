import { useEffect, useMemo, useState } from 'react';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import type { CodexCapabilityV1 } from '@ip-studio/contracts/codex';
import type { CodexPatchProposalV1 } from '@ip-studio/contracts/canvas-patch';
import { api } from '../../lib/api';
import { PatchPreview } from './PatchPreview';

export interface CodexAssistantProps {
  episodeId: string;
  currentRevision: number;
  currentDocument: CanvasDocumentV1 | null;
  onApplied?: (document: CanvasDocumentV1) => void;
  onManualEdit: () => void;
}

export function CodexAssistant({
  episodeId,
  currentRevision,
  currentDocument,
  onApplied,
  onManualEdit,
}: CodexAssistantProps) {
  const [capability, setCapability] = useState<CodexCapabilityV1 | null>(null);
  const [proposals, setProposals] = useState<CodexPatchProposalV1[]>([]);
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([api.getCodexCapabilities(), api.getCodexPatchProposals(episodeId)])
      .then(([report, items]) => {
        if (!active) return;
        setCapability(report);
        setProposals(items);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : '无法读取本机 Codex 状态');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [episodeId]);

  const pendingProposal = useMemo(
    () => proposals.find((proposal) => proposal.status === 'pending_approval'),
    [proposals],
  );
  const canPropose = Boolean(
    capability?.codex_path
      && (capability.status === 'available' || capability.status === 'unsupported'),
  );
  const capabilityMessage = capability
    ? canPropose
      ? `本机 Codex CLI 可用于只读文字建议；ImageGen：${capability.reason}`
      : capability.reason
    : '本机 Codex 不可用';

  async function createProposal() {
    setBusy(true);
    setError('');
    try {
      const proposal = await api.proposeCodexPatch(episodeId, instruction);
      setProposals((items) => [proposal, ...items.filter((item) => item.patch_id !== proposal.patch_id)]);
      setInstruction('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法生成 Codex Patch 建议；请继续手动编辑。');
    } finally {
      setBusy(false);
    }
  }

  async function approveProposal(proposal: CodexPatchProposalV1) {
    setBusy(true);
    setError('');
    try {
      const reviewed = await api.approveCodexPatch(
        proposal.patch_id,
        proposal.base_revision,
        proposal.approval_id,
      );
      setProposals((items) => items.map((item) => item.patch_id === reviewed.patch_id ? reviewed : item));
      const current = await api.getEpisodeDocument(episodeId);
      if (current.document) onApplied?.(current.document);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法批准 Patch；画布没有被覆盖。');
    } finally {
      setBusy(false);
    }
  }

  async function rejectProposal(proposal: CodexPatchProposalV1) {
    setBusy(true);
    setError('');
    try {
      const reviewed = await api.rejectCodexPatch(proposal.patch_id, '由管理员拒绝');
      setProposals((items) => items.map((item) => item.patch_id === reviewed.patch_id ? reviewed : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法拒绝 Patch');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="codex-assistant" aria-label="Codex 画布助手">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">LOCAL CODEX · HUMAN APPROVAL REQUIRED</p>
          <h2>Codex 画布建议</h2>
        </div>
        <span role="status">
          {loading ? '正在检查…' : capabilityMessage}
        </span>
      </div>
      <p className="generation-task-note">
        所有 Codex 修改都需要人工批准；建议以当前 document revision 为基础，批准后才会写入新 revision。拒绝不会修改画布。
      </p>
      {!loading && capability && !canPropose && (
        <p className="form-error" role="status">{capability.reason} 可继续直接手动编辑画布。</p>
      )}
      {!pendingProposal && (
        <>
          <label className="codex-patch-instruction">
            想修改什么
            <textarea
              aria-label="Codex 修改要求"
              rows={3}
              maxLength={4000}
              value={instruction}
              onChange={(event) => setInstruction(event.currentTarget.value)}
              placeholder="例如：把第一格朋友的消息改得更犹豫，但不要修改右侧卡仔的回复。"
            />
          </label>
          <button
            className="button button-primary"
            type="button"
            disabled={!canPropose || loading || busy || !instruction.trim()}
            onClick={() => void createProposal()}
          >
            {busy ? '正在生成结构化建议…' : '生成 Patch 建议'}
          </button>
        </>
      )}
      {pendingProposal && (
        <PatchPreview
          proposal={pendingProposal}
          currentDocument={currentDocument}
          currentRevision={currentRevision}
          busy={busy}
          onApprove={() => void approveProposal(pendingProposal)}
          onReject={() => void rejectProposal(pendingProposal)}
        />
      )}
      <button className="button button-secondary" type="button" onClick={onManualEdit}>
        继续手动编辑画布
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
