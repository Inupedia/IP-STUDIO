import { useState } from 'react';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import { api } from '../../lib/api';
import { renderEpisodePagesToPng } from './exportPng';

export interface ExportPanelProps {
  episodeId: string;
  currentRevision: number;
  canvasDocument: CanvasDocumentV1;
  brand: BrandTemplateV1;
  assetSources: Record<string, string>;
}

export function ExportPanel({
  episodeId,
  currentRevision,
  canvasDocument,
  brand,
  assetSources,
}: ExportPanelProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function exportPngPages() {
    if (canvasDocument.revision !== currentRevision) {
      setError('画布尚未与当前 revision 同步保存，请先保存后再导出。');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
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
      setBusy(false);
    }
  }

  return (
    <section className="export-panel" aria-label="PNG 导出">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">PNG · ORIGINAL PAGE SIZE</p>
          <h3>导出 PNG 图组</h3>
        </div>
        <span>{canvasDocument.pages.length} 页 · revision {currentRevision}</span>
      </div>
      <p className="generation-task-note">导出会按页面顺序生成原始像素 PNG，并保存为绑定当前 revision 的 ZIP；网格与安全区辅助线不会进入成品。</p>
      <button className="button button-primary" type="button" disabled={busy} onClick={() => void exportPngPages()}>
        {busy ? '正在渲染并打包…' : '导出 PNG 图组'}
      </button>
      {message && <p className="production-success" role="status">{message}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
