import { createElement } from 'react';
import { createRoot } from 'react-dom/client';
import type Konva from 'konva';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import { ExportPageStage } from './ExportPageStage';

export interface RenderPageOptions {
  brand: BrandTemplateV1;
  assetSources: Record<string, string>;
}

function requiredAssetVersionIds(
  page: CanvasDocumentV1['pages'][number],
  brand: BrandTemplateV1,
): string[] {
  const panelAssetIds = page.panels.flatMap((panel) => panel.elements.flatMap((element) =>
    (element.type === 'image' || element.type === 'sticker') ? [element.asset_version_id] : [],
  ));
  const brandAssetIds = brand.locked_elements.flatMap((element) => element.asset_version_id
    ? [element.asset_version_id]
    : []);
  return [...new Set([...brandAssetIds, ...panelAssetIds])];
}

async function preloadImage(source: string, assetVersionId: string): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const image = new window.Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => {
      if (image.naturalWidth <= 0 || image.naturalHeight <= 0) {
        reject(new Error(`素材 ${assetVersionId} 无法解码`));
        return;
      }
      resolve();
    };
    image.onerror = () => reject(new Error(`素材 ${assetVersionId} 加载失败，未生成导出文件`));
    image.src = source;
    if (image.complete) {
      if (image.naturalWidth > 0 && image.naturalHeight > 0) resolve();
      else reject(new Error(`素材 ${assetVersionId} 无法解码`));
    }
  });
}

function pngDataUrlToBlob(dataUrl: string): Blob {
  const match = /^data:image\/png;base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl);
  if (!match) throw new Error('画布没有返回有效 PNG 数据');
  const binary = window.atob(match[1]);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new Blob([bytes], { type: 'image/png' });
}

function renderStageToBlob(
  page: CanvasDocumentV1['pages'][number],
  document: CanvasDocumentV1,
  options: RenderPageOptions,
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const host = window.document.createElement('div');
    host.setAttribute('aria-hidden', 'true');
    Object.assign(host.style, {
      position: 'fixed',
      left: '-10000px',
      top: '0',
      width: `${page.width}px`,
      height: `${page.height}px`,
      overflow: 'hidden',
      pointerEvents: 'none',
    });
    window.document.body.append(host);
    const root = createRoot(host);
    let settled = false;
    const timeout = window.setTimeout(() => finishError(new Error('PNG 页面渲染超时')), 15_000);

    function cleanUp() {
      window.clearTimeout(timeout);
      queueMicrotask(() => {
        root.unmount();
        host.remove();
      });
    }

    function finishError(error: Error) {
      if (settled) return;
      settled = true;
      cleanUp();
      reject(error);
    }

    function finishStage(stage: Konva.Stage) {
      if (settled) return;
      try {
        if (stage.width() !== page.width || stage.height() !== page.height) {
          throw new Error('导出画布尺寸与页面原始尺寸不一致');
        }
        const dataUrl = stage.toDataURL({ pixelRatio: 1, mimeType: 'image/png' });
        const blob = pngDataUrlToBlob(dataUrl);
        settled = true;
        cleanUp();
        resolve(blob);
      } catch (cause) {
        finishError(cause instanceof Error ? cause : new Error('PNG 页面渲染失败'));
      }
    }

    try {
      root.render(createElement(ExportPageStage, {
        page,
        brand: options.brand,
        assetSources: options.assetSources,
        title: document.dynamic_fields.title,
        episodeNumber: document.dynamic_fields.episode_number,
        onReady: finishStage,
        onError: finishError,
      }));
    } catch (cause) {
      finishError(cause instanceof Error ? cause : new Error('PNG 页面渲染失败'));
    }
  });
}

export async function renderPageToPng(
  canvasDocument: CanvasDocumentV1,
  pageId: string,
  options: RenderPageOptions,
): Promise<Blob> {
  const page = canvasDocument.pages.find((candidate) => candidate.id === pageId);
  if (!page) throw new Error(`Canvas page ${pageId} was not found`);
  const missingAssetIds = requiredAssetVersionIds(page, options.brand)
    .filter((assetVersionId) => !options.assetSources[assetVersionId]);
  if (missingAssetIds.length > 0) {
    throw new Error(`缺少已批准素材，无法导出：${missingAssetIds.join(', ')}`);
  }
  await Promise.all(requiredAssetVersionIds(page, options.brand).map((assetVersionId) =>
    preloadImage(options.assetSources[assetVersionId], assetVersionId),
  ));
  return renderStageToBlob(page, canvasDocument, options);
}

export async function renderEpisodePagesToPng(
  canvasDocument: CanvasDocumentV1,
  options: RenderPageOptions,
): Promise<Blob[]> {
  const orderedPages = [...canvasDocument.pages].sort((first, second) => first.order - second.order);
  const output: Blob[] = [];
  for (const page of orderedPages) output.push(await renderPageToPng(canvasDocument, page.id, options));
  return output;
}
