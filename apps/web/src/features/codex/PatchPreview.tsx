import type { CanvasDocumentV1, CanvasElementV1 } from '@ip-studio/contracts/canvas';
import type { CanvasPatchOperationV1, CodexPatchProposalV1 } from '@ip-studio/contracts/canvas-patch';

export interface PatchPreviewProps {
  proposal: CodexPatchProposalV1;
  currentDocument: CanvasDocumentV1 | null;
  currentRevision: number;
  busy?: boolean;
  onApprove?: () => void;
  onReject?: () => void;
}

function findElement(document: CanvasDocumentV1 | null, elementId: string): CanvasElementV1 | undefined {
  return document?.pages.flatMap((page) => page.panels.flatMap((panel) => panel.elements))
    .find((element) => element.id === elementId);
}

function describeOperation(operation: CanvasPatchOperationV1, document: CanvasDocumentV1 | null): string {
  if (operation.op === 'set_text') {
    const element = findElement(document, operation.element_id);
    const oldText = element && 'props' in element && 'text' in element.props ? element.props.text : '（原文字）';
    return `文字：${oldText} → ${operation.text}`;
  }
  if (operation.op === 'set_transform') {
    const previous = findElement(document, operation.element_id)?.transform;
    const position = (value: typeof operation.transform | undefined) => value
      ? `x ${value.x}, y ${value.y}, ${value.width} × ${value.height}, ${value.rotation}°`
      : '（原位置）';
    return `位置与尺寸：${position(previous)} → ${position(operation.transform)}`;
  }
  if (operation.op === 'replace_image_asset') {
    const previous = findElement(document, operation.element_id);
    const version = previous && 'asset_version_id' in previous ? previous.asset_version_id : '（原素材）';
    return `替换图片版本：${version} → ${operation.asset_version_id}`;
  }
  if (operation.op === 'insert_element') {
    const text = 'props' in operation.element && 'text' in operation.element.props
      ? `：“${operation.element.props.text}”`
      : '';
    return `新增 ${operation.element.type}${text} 到 Panel ${operation.panel_id}`;
  }
  const removed = findElement(document, operation.element_id);
  const label = removed && 'props' in removed && 'text' in removed.props
    ? `：“${removed.props.text}”`
    : '';
  return `移除 ${removed?.type ?? '画布元素'}${label}`;
}

export function PatchPreview({
  proposal,
  currentDocument,
  currentRevision,
  busy = false,
  onApprove,
  onReject,
}: PatchPreviewProps) {
  const stale = currentRevision !== proposal.base_revision;
  return (
    <article className="patch-preview" aria-label="Codex Patch 预览">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">REVISION {proposal.base_revision} · {proposal.patch.operations.length} OPERATIONS</p>
          <h3>{proposal.patch.summary}</h3>
        </div>
        <span>{proposal.status === 'pending_approval' ? '待人工批准' : proposal.status === 'approved' ? '已批准' : '已拒绝'}</span>
      </div>
      {stale && proposal.status === 'pending_approval' && (
        <p className="form-error" role="alert">当前画布已更新到 revision {currentRevision}；此建议已过期，请从最新版本重新生成。</p>
      )}
      <ol className="patch-preview-operations">
        {proposal.patch.operations.map((operation, index) => (
          <li key={`${operation.op}:${index}`}>{describeOperation(operation, currentDocument)}</li>
        ))}
      </ol>
      <details>
        <summary>查看批准后完整画布 JSON</summary>
        <pre>{JSON.stringify(proposal.preview_document, null, 2)}</pre>
      </details>
      {proposal.review_note && <p>审核意见：{proposal.review_note}</p>}
      {proposal.status === 'pending_approval' && (
        <div className="generation-task-actions">
          <button
            className="button button-primary"
            type="button"
            disabled={busy || stale}
            onClick={onApprove}
          >
            批准并写入 revision {proposal.base_revision + 1}
          </button>
          <button className="button button-secondary" type="button" disabled={busy} onClick={onReject}>
            拒绝 Patch
          </button>
        </div>
      )}
    </article>
  );
}
