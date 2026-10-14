import { useState } from 'react';
import type { GenerationCandidateV1, GenerationTaskV1 } from '@ip-studio/contracts/generation';
import type { AssetType } from '@ip-studio/contracts/domain';
import { api } from '../../lib/api';
import { useClipboardImage } from './useClipboardImage';

const SUPPORTED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;
const EXTENSION_BY_MIME: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/webp': 'webp',
};

export interface ImportAssetDropzoneProps {
  ipId: string;
  task: GenerationTaskV1;
  activePanelId: string | null;
  onImported: (candidate: GenerationCandidateV1) => void;
}

export function ImportAssetDropzone({ ipId, task, activePanelId, onImported }: ImportAssetDropzoneProps) {
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function importFile(file: File, targetPanelId: string | null) {
    setMessage('');
    setError('');
    if (!targetPanelId) {
      setError('请先在画布中选择目标画格。');
      return;
    }
    if (targetPanelId !== task.panel_id) {
      setError('此任务绑定的画格不是当前选中画格；请切换到任务对应的画格再导入。');
      return;
    }
    if (!['waiting_manual_generation', 'asset_imported'].includes(task.status)) {
      setError('请先将任务切换到人工生成中，再导入图片。');
      return;
    }
    if (!SUPPORTED_IMAGE_TYPES.has(file.type)) {
      setError('只支持 PNG、JPEG 和 WebP 图片。');
      return;
    }
    if (file.size === 0 || file.size > MAX_IMAGE_BYTES) {
      setError('图片不能为空且不能超过 25 MiB。');
      return;
    }

    setBusy(true);
    setError('');
    let assetVersionId: string | null = null;
    try {
      const name = file.name.replace(/\.[^.]+$/, '').trim().slice(0, 200) || '生图候选';
      const assetType: AssetType = 'composite_panel';
      const asset = await api.uploadAsset(file, ipId, name, assetType);
      assetVersionId = asset.asset_version_id;
      const candidate = await api.importGenerationCandidate(task.task_id, assetVersionId);
      onImported(candidate);
      setMessage('已导入为待审核候选；正式画格保持不变。');
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : '导入失败';
      setError(assetVersionId
        ? `图片已上传为候选素材，但还没有绑定到任务：${detail}`
        : detail);
    } finally {
      setBusy(false);
    }
  }

  async function readClipboard() {
    setMessage('');
    setError('');
    if (!navigator.clipboard?.read) {
      setError('当前浏览器不支持读取剪贴板；可以按 Ctrl+V、拖放图片或选择文件。');
      return;
    }
    try {
      const items = await navigator.clipboard.read();
      for (const item of items) {
        const mime = [...item.types].find((type) => SUPPORTED_IMAGE_TYPES.has(type));
        if (!mime) continue;
        const blob = await item.getType(mime);
        const file = new File([blob], `clipboard-image.${EXTENSION_BY_MIME[mime]}`, { type: mime });
        await importFile(file, activePanelId);
        return;
      }
      setError('剪贴板中没有 PNG、JPEG 或 WebP 图片。');
    } catch (cause) {
      const denied = cause instanceof DOMException
        && (cause.name === 'NotAllowedError' || cause.name === 'SecurityError');
      setError(denied
        ? '浏览器拒绝读取剪贴板；请在浏览器提示中授予权限，或使用 Ctrl+V、拖放图片和文件选择。'
        : cause instanceof Error ? cause.message : '无法读取剪贴板图片');
    }
  }

  const clipboard = useClipboardImage(activePanelId, (targetPanelId, file) =>
    importFile(file, targetPanelId));
  const visibleError = error || clipboard.error;

  return (
    <section className="import-asset-dropzone" aria-label="导入生图候选">
      <div
        className={`import-asset-target${dragging ? ' import-asset-target-dragging' : ''}`}
        role="group"
        aria-label="拖入候选图片"
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const file = event.dataTransfer.files[0];
          if (file) void importFile(file, activePanelId);
        }}
      >
        <p className="eyebrow">CANDIDATE IMPORT · PANEL {task.panel_id.slice(0, 8)}</p>
        <strong>把生图结果放回对应画格</strong>
        <span>先选中任务绑定的画格，再拖入、选择图片，或粘贴剪贴板中的图片。</span>
        <button
          className="button button-secondary"
          type="button"
          disabled={busy}
          onClick={() => void readClipboard()}
        >
          从剪贴板读取
        </button>
        <label className="button button-secondary import-asset-select">
          {busy ? '正在导入…' : '选择图片'}
          <input
            aria-label="导入候选图片"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={busy}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              event.currentTarget.value = '';
              if (file) void importFile(file, activePanelId);
            }}
          />
        </label>
      </div>
      {message && <p className="production-success" role="status">{message}</p>}
      {visibleError && <p className="form-error" role="alert">{visibleError}</p>}
    </section>
  );
}
