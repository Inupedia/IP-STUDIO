import { useState } from 'react';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import { api } from '../../lib/api';
import { renderEpisodePagesToPng } from './exportPng';
import { exportEpisodePptx } from './exportPptx';

export interface ExportPanelProps {
  episodeId: string;
  currentRevision: number;
  canvasDocument: CanvasDocumentV1;
  brand: BrandTemplateV1;
  assetSources: Record<string, string>;
  isSaved?: boolean;
}

export function ExportPanel({
  episodeId,
  currentRevision,
  canvasDocument,
  brand,
  assetSources,
  isSaved = true,
}: ExportPanelProps) {
  const [busyFormat, setBusyFormat] = useState<'png' | 'pptx' | null>(null);
  const busy = busyFormat !== null;
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);

  async function exportPngPages() {
    if (!isSaved) {
      setError('请先保存当前画布，再导出。');
      return;
    }
    if (canvasDocument.revision !== currentRevision) {
      setError('画布尚未与当前 revision 同步保存，请先保存后再导出。');
      return;
    }
    setBusyFormat('png');
    setError('');
    setMessage('');
    setWarnings([]);
    try {
      const pages = await renderEpisodePagesToPng(canvasDocument, { brand, assetSources });
      const exportJob = await api.createPngExport(episodeId, currentRevision, pages);
      const archive = await api.downloadExport(exportJob.id);
      const url = URL.createObjectURL(archive);
      const link = window.document.createElement('a');
      link.href = url;
      link.download = `episode-r${currentRevision}-pages.zip`;
      window.document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setMessage(`已导出 revision ${currentRevision} 的 ${exportJob.page_count} 页 PNG。`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'PNG 导出失败，请检查素材后重试。');
    } finally {
      setBusyFormat(null);
    }
  }

  async function exportPptx() {
    if (!isSaved) {
      setError('请先保存当前画布，再导出。');
      return;
    }
    if (canvasDocument.revision !== currentRevision) {
      setError('画布尚未与当前 revision 同步保存，请先保存后再导出。');
      return;
    }
    setBusyFormat('pptx');
    setError('');
    setMessage('');
    setWarnings([]);
    try {
      const result = await exportEpisodePptx(canvasDocument, { brand, assetSources });
      const url = URL.createObjectURL(result.blob);
      const link = window.document.createElement('a');
      link.href = url;
      link.download = `episode-r${currentRevision}-editable.pptx`;
      window.document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 100);
      setWarnings(result.warnings);
      setMessage(`已导出 revision ${currentRevision} 的可编辑 PPTX。`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'PPTX 导出失败，请检查素材后重试。');
    } finally {
      setBusyFormat(null);
    }
  }

  return (
    <section className="export-panel" aria-label="漫画导出">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">PNG · EDITABLE PPTX</p>
          <h3>导出漫画</h3>
        </div>
        <span>{canvasDocument.pages.length} 页 · revision {currentRevision}</span>
      </div>
      <p className="generation-task-note">PNG 会按页面顺序生成原始像素图组，PPTX 会将文字、气泡、形状与图片分别写成对象；辅助线不会进入导出。</p>
      <div className="production-action-row">
        <button className="button button-primary" type="button" disabled={busy || !isSaved} onClick={() => void exportPngPages()}>
          {busyFormat === 'png' ? '正在渲染并打包…' : '导出 PNG 图组'}
        </button>
        <button className="button button-secondary" type="button" disabled={busy || !isSaved} onClick={() => void exportPptx()}>
          {busyFormat === 'pptx' ? '正在生成…' : '导出可编辑 PPTX'}
        </button>
      </div>
      {!isSaved && <p className="generation-task-note">保存后才能导出当前 revision。</p>}
      {message && <p className="production-success" role="status">{message}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {warnings.length > 0 && (
        <ul className="generation-task-note" aria-label="PPTX 导出提示">
          {warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      )}
    </section>
  );
}
