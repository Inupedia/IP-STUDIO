import type PptxGenJs from 'pptxgenjs';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import type {
  PptxContext,
  PptxImageObject,
  PptxObject,
  PptxShapeObject,
  PptxTextObject,
} from './pptxMapper';
import { mapCanvasElementToPptx } from './pptxMapper';

const PAGE_WIDTH_INCHES = 8.5;
const PAGE_HEIGHT_LIMIT_INCHES = 15;
const FALLBACK_BACKGROUND = 'FFFEFA';

export interface ExportPptxOptions {
  brand: BrandTemplateV1;
  assetSources: Record<string, string>;
}

export interface PptxExportResult {
  blob: Blob;
  warnings: string[];
}

interface PresentationFrame {
  width: number;
  height: number;
}

function requiredAssetVersionIds(document: CanvasDocumentV1, brand: BrandTemplateV1): string[] {
  const pageAssetIds = document.pages.flatMap((page) => page.panels.flatMap((panel) =>
    panel.elements.flatMap((element) =>
      element.type === 'image' || element.type === 'sticker' ? [element.asset_version_id] : [],
    ),
  ));
  const brandAssetIds = brand.locked_elements.flatMap((element) =>
    element.asset_version_id ? [element.asset_version_id] : [],
  );
  return [...new Set([...pageAssetIds, ...brandAssetIds])];
}

function presentationFrame(document: CanvasDocumentV1): PresentationFrame & { pixelsToInches: number } {
  const maxWidth = Math.max(...document.pages.map((page) => page.width));
  const maxHeight = Math.max(...document.pages.map((page) => page.height));
  const pixelsToInches = Math.min(PAGE_WIDTH_INCHES / maxWidth, PAGE_HEIGHT_LIMIT_INCHES / maxHeight);
  const width = maxWidth * pixelsToInches;
  const height = maxHeight * pixelsToInches;
  if (width < 1 || height < 1) {
    throw new Error('页面比例超出 PPTX 支持范围，无法生成演示文稿。');
  }
  return { width, height, pixelsToInches };
}

function safeColor(color: string | null | undefined, fallback = FALLBACK_BACKGROUND): string {
  if (!color) return fallback;
  const value = color.replace(/^#/, '');
  if (/^[0-9a-f]{6}$/i.test(value)) return value.toUpperCase();
  if (/^[0-9a-f]{3}$/i.test(value)) return value.split('').map((part) => part + part).join('').toUpperCase();
  return fallback;
}

function objectName(id: string, suffix: string): string {
  return `ipstudio-${id.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 40)}-${suffix}`;
}

function brandShape(
  id: string,
  suffix: string,
  x: number,
  y: number,
  width: number,
  height: number,
  fill: string | null | undefined,
  opacity: number,
  context: PptxContext,
): PptxShapeObject {
  return {
    kind: 'shape',
    shape: 'rect',
    objectName: objectName(id, suffix),
    x: context.offsetX + x * context.pixelsToInches,
    y: context.offsetY + y * context.pixelsToInches,
    w: width * context.pixelsToInches,
    h: height * context.pixelsToInches,
    rotate: 0,
    opacity,
    fill: fill ? safeColor(fill) : null,
    stroke: null,
    lineWidth: 0,
  };
}

function brandImage(
  id: string,
  assetVersionId: string,
  x: number,
  y: number,
  width: number,
  height: number,
  opacity: number,
  context: PptxContext,
): PptxImageObject | null {
  const data = context.assetSources[assetVersionId];
  if (!data) return null;
  return {
    kind: 'image',
    objectName: objectName(id, 'brand-image'),
    x: context.offsetX + x * context.pixelsToInches,
    y: context.offsetY + y * context.pixelsToInches,
    w: width * context.pixelsToInches,
    h: height * context.pixelsToInches,
    rotate: 0,
    opacity,
    assetVersionId,
    data,
  };
}

function brandText(
  id: string,
  suffix: string,
  text: string,
  slot: BrandTemplateV1['dynamic_slots']['title'],
  context: PptxContext,
): PptxTextObject {
  const estimatedWidth = [...text].reduce(
    (sum, character) => sum + slot.font_size * (/^[\u0000-\u00ff]$/.test(character) ? 0.55 : 1),
    0,
  );
  if (estimatedWidth > slot.width || slot.font_size * 1.2 > slot.height) {
    context.warnings.push(`品牌文字「${text}」可能超出标题栏；请检查 PPTX 预览。`);
  }
  return {
    kind: 'text',
    objectName: objectName(id, suffix),
    x: context.offsetX + slot.x * context.pixelsToInches,
    y: context.offsetY + slot.y * context.pixelsToInches,
    w: slot.width * context.pixelsToInches,
    h: slot.height * context.pixelsToInches,
    rotate: 0,
    opacity: 1,
    text,
    fontFace: slot.font_family,
    fontSize: slot.font_size * context.pixelsToInches * 72,
    bold: false,
    color: safeColor(slot.color, '242923'),
    align: slot.align,
    lineSpacingMultiple: 1,
  };
}

function addShape(slide: PptxGenJs.Slide, pptx: PptxGenJs, item: PptxShapeObject): void {
  const shapeName = pptx.ShapeType[item.shape as keyof typeof pptx.ShapeType];
  slide.addShape(shapeName, {
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    rotate: item.rotate,
    objectName: item.objectName,
    fill: item.fill
      ? { color: item.fill, transparency: Math.round((1 - item.opacity) * 100) }
      : { color: 'FFFFFF', transparency: 100 },
    line: item.stroke
      ? {
          color: item.stroke,
          width: Math.max(0.1, item.lineWidth),
          transparency: Math.round((1 - item.opacity) * 100),
          endArrowType: item.endArrow ? 'triangle' : 'none',
        }
      : { color: 'FFFFFF', width: 0.1, transparency: 100 },
  });
}

function addText(slide: PptxGenJs.Slide, item: PptxTextObject): void {
  slide.addText(item.text, {
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    rotate: item.rotate,
    objectName: item.objectName,
    fontFace: item.fontFace,
    fontSize: Math.max(1, item.fontSize),
    bold: item.bold,
    color: item.color,
    transparency: Math.round((1 - item.opacity) * 100),
    align: item.align,
    valign: 'middle',
    lineSpacingMultiple: item.lineSpacingMultiple,
    fit: 'shrink',
    margin: 0,
    lang: 'zh-CN',
  });
}

function decodeDataUrl(source: string): Blob | null {
  const match = /^data:(image\/[a-zA-Z0-9.+-]+);base64,([a-zA-Z0-9+/=]+)$/.exec(source);
  if (!match) return null;
  const binary = window.atob(match[2]);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new Blob([bytes], { type: match[1] });
}

async function fetchImageBlob(source: string): Promise<Blob> {
  const decoded = decodeDataUrl(source);
  if (decoded) return decoded;
  const response = await fetch(source, { credentials: 'same-origin' });
  if (!response.ok) throw new Error(`素材加载失败（HTTP ${response.status}）`);
  const blob = await response.blob();
  if (!blob.type.startsWith('image/')) throw new Error('素材不是受支持的图片');
  return blob;
}

function toBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 32 * 1024) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 32 * 1024));
  }
  return btoa(binary);
}

async function imageDataForPptx(item: PptxImageObject): Promise<string> {
  const directDataUrl = /^data:(image\/(?:png|jpeg));base64,([a-zA-Z0-9+/=]+)$/.exec(item.data);
  const sourceBlob = await fetchImageBlob(item.data);
  const crop = item.crop ?? { x: 0, y: 0, width: 1, height: 1 };
  const cropped = crop.x !== 0 || crop.y !== 0 || crop.width !== 1 || crop.height !== 1;
  const needsPng = sourceBlob.type === 'image/webp' || sourceBlob.type === 'image/gif';
  if (!cropped && !needsPng && directDataUrl) return `${directDataUrl[1]};base64,${directDataUrl[2]}`;
  if (!cropped && !needsPng) {
    const mime = sourceBlob.type === 'image/jpeg' ? 'image/jpeg' : 'image/png';
    return `${mime};base64,${toBase64(new Uint8Array(await sourceBlob.arrayBuffer()))}`;
  }

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(sourceBlob);
  } catch (error) {
    throw new Error(`素材 ${item.assetVersionId} 无法为 PPTX 解码：${error instanceof Error ? error.message : '未知错误'}`);
  }
  const sourceX = Math.round(bitmap.width * crop.x);
  const sourceY = Math.round(bitmap.height * crop.y);
  const sourceWidth = Math.max(1, Math.round(bitmap.width * crop.width));
  const sourceHeight = Math.max(1, Math.round(bitmap.height * crop.height));
  const canvas = window.document.createElement('canvas');
  canvas.width = sourceWidth;
  canvas.height = sourceHeight;
  const context = canvas.getContext('2d');
  if (!context) {
    bitmap.close();
    throw new Error(`素材 ${item.assetVersionId} 无法转换为 PowerPoint 图片`);
  }
  context.drawImage(bitmap, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, sourceWidth, sourceHeight);
  bitmap.close();
  const dataUrl = canvas.toDataURL('image/png');
  return dataUrl.replace(/^data:/, '');
}

async function addObjectsToSlide(
  slide: PptxGenJs.Slide,
  pptx: PptxGenJs,
  objects: PptxObject[],
): Promise<void> {
  for (const item of objects) {
    if (item.kind === 'shape') {
      addShape(slide, pptx, item);
    } else if (item.kind === 'text') {
      addText(slide, item);
    } else {
      slide.addImage({
        data: await imageDataForPptx(item),
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h,
        rotate: item.rotate,
        transparency: Math.round((1 - item.opacity) * 100),
        objectName: item.objectName,
        altText: `IP Studio asset ${item.assetVersionId}`,
      });
    }
  }
}

function fitPageToFrame(page: CanvasDocumentV1['pages'][number], frame: PresentationFrame, warnings: string[]) {
  const scale = Math.min(frame.width / page.width, frame.height / page.height);
  const width = page.width * scale;
  const height = page.height * scale;
  if (width !== frame.width || height !== frame.height) {
    warnings.push(`第 ${page.order} 页尺寸与 PPTX 幻灯片比例不同，已等比居中留白。`);
  }
  return {
    pixelsToInches: scale,
    offsetX: (frame.width - width) / 2,
    offsetY: (frame.height - height) / 2,
  };
}

function assertBrandAndAssets(
  document: CanvasDocumentV1,
  brand: BrandTemplateV1,
  assetSources: Record<string, string>,
): void {
  for (const page of document.pages) {
    if (page.width !== brand.width || page.height !== brand.height) {
      throw new Error('页面尺寸与锁定品牌模板不一致，PPTX 导出已停止。');
    }
  }
  const missing = requiredAssetVersionIds(document, brand).filter((id) => !assetSources[id]);
  if (missing.length) throw new Error(`缺少素材，无法导出 PPTX：${missing.join(', ')}`);
}

export async function exportEpisodePptx(
  document: CanvasDocumentV1,
  options: ExportPptxOptions,
): Promise<PptxExportResult> {
  assertBrandAndAssets(document, options.brand, options.assetSources);
  const orderedPages = [...document.pages].sort((first, second) => first.order - second.order);
  const frame = presentationFrame(document);
  const warnings = new Set<string>([
    'PPTX 与网页画布的字体和自动换行可能不同；请打开文件检查预览。',
  ]);
  const PptxGenJS = (await import('pptxgenjs')).default;
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'IP_STUDIO_PORTRAIT', width: frame.width, height: frame.height });
  pptx.layout = 'IP_STUDIO_PORTRAIT';
  pptx.author = 'IP Studio';
  pptx.subject = `Episode ${document.episode_id} revision ${document.revision}`;
  pptx.title = document.dynamic_fields.title || `Episode ${document.dynamic_fields.episode_number}`;
  pptx.theme = {
    headFontFace: 'Arial',
    bodyFontFace: 'Arial',
  };

  for (const page of orderedPages) {
    const slide = pptx.addSlide();
    const pageWarnings: string[] = [];
    const fitted = fitPageToFrame(page, frame, pageWarnings);
    const pageContext: PptxContext = {
      pixelsToInches: fitted.pixelsToInches,
      offsetX: fitted.offsetX,
      offsetY: fitted.offsetY,
      assetSources: options.assetSources,
      warnings: pageWarnings,
    };
    slide.background = { color: FALLBACK_BACKGROUND };
    await addObjectsToSlide(slide, pptx, [brandShape(
      `page-${page.id}`, 'canvas-background', 0, 0, page.width, page.height,
      '#fffefa', 1, pageContext,
    )]);

    for (const element of options.brand.locked_elements.filter((item) => item.kind === 'background')) {
      const image = element.asset_version_id
        ? brandImage(element.id, element.asset_version_id, element.x, element.y,
          element.width, element.height, element.opacity, pageContext)
        : null;
      await addObjectsToSlide(slide, pptx, [image ?? brandShape(
        element.id, 'brand-background', element.x, element.y, element.width, element.height,
        element.fill, element.opacity, pageContext,
      )]);
    }

    for (const panel of page.panels) {
      const panelFrame: PptxShapeObject = {
        kind: 'shape',
        shape: 'rect',
        objectName: objectName(panel.id, 'panel-frame'),
        x: fitted.offsetX + panel.rect.x * fitted.pixelsToInches,
        y: fitted.offsetY + panel.rect.y * fitted.pixelsToInches,
        w: panel.rect.width * fitted.pixelsToInches,
        h: panel.rect.height * fitted.pixelsToInches,
        rotate: 0,
        opacity: 1,
        fill: 'FFFEFA',
        stroke: '4D514A',
        lineWidth: 2 * fitted.pixelsToInches * 72,
      };
      await addObjectsToSlide(slide, pptx, [panelFrame]);
      const panelContext = {
        ...pageContext,
        offsetX: fitted.offsetX + panel.rect.x * fitted.pixelsToInches,
        offsetY: fitted.offsetY + panel.rect.y * fitted.pixelsToInches,
      };
      for (const element of [...panel.elements].sort((first, second) => first.z_index - second.z_index)) {
        if (
          element.transform.x < 0
          || element.transform.y < 0
          || element.transform.x + element.transform.width > panel.rect.width
          || element.transform.y + element.transform.height > panel.rect.height
        ) {
          pageWarnings.push(`元素 ${element.id} 超出画格边界，PPTX 中不会自动裁切画格内容。`);
        }
        await addObjectsToSlide(
          slide, pptx, mapCanvasElementToPptx(element, panelContext),
        );
      }
    }

    for (const element of options.brand.locked_elements.filter((item) => item.kind !== 'background')) {
      const image = element.asset_version_id
        ? brandImage(element.id, element.asset_version_id, element.x, element.y,
          element.width, element.height, element.opacity, pageContext)
        : null;
      await addObjectsToSlide(slide, pptx, [image ?? brandShape(
        element.id, 'brand-shell', element.x, element.y, element.width, element.height,
        element.fill, element.opacity, pageContext,
      )]);
    }
    await addObjectsToSlide(slide, pptx, [
      brandText('brand-title', 'dynamic-title', document.dynamic_fields.title,
        options.brand.dynamic_slots.title, pageContext),
      brandText('brand-episode', 'dynamic-episode', document.dynamic_fields.episode_number,
        options.brand.dynamic_slots.episode_number, pageContext),
    ]);
    for (const warning of pageWarnings) warnings.add(warning);
  }

  const output = await pptx.write({ outputType: 'blob' });
  if (!(output instanceof Blob)) throw new Error('PPTX 生成器没有返回有效文件');
  return { blob: output, warnings: [...warnings] };
}
