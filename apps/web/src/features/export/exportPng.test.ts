import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import canvasFixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import { BrandTemplateV1Schema } from '@ip-studio/contracts/brand';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import { renderEpisodePagesToPng, renderPageToPng } from './exportPng';

const exportRenderer = vi.hoisted(() => ({ pages: [] as unknown[], brand: null as unknown, stage: null as unknown }));

vi.mock('./ExportPageStage', async () => {
  const React = await import('react');
  return {
    ExportPageStage: (props: {
      page: { width: number; height: number };
      brand: unknown;
      assetSources: Record<string, string>;
      title: string;
      episodeNumber: string;
      onReady: (stage: unknown) => void;
    }) => {
      React.useEffect(() => {
        const stage = {
          width: () => props.page.width,
          height: () => props.page.height,
          batchDraw: vi.fn(),
          toDataURL: vi.fn(() => 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='),
        };
        exportRenderer.pages.push(props.page);
        exportRenderer.brand = props.brand;
        exportRenderer.stage = stage;
        props.onReady(stage);
      }, []);
      return null;
    },
  };
});

const brand = BrandTemplateV1Schema.parse({
  schema_version: '1.0',
  width: 1080,
  height: 1440,
  locked_elements: [
    { id: 'fixed-logo', kind: 'logo', locked: true, x: 48, y: 40, width: 120, height: 60, fill: '#243a2d' },
    { id: 'fixed-footer', kind: 'footer', locked: true, x: 48, y: 1380, width: 984, height: 24, fill: '#eeeeee' },
  ],
  dynamic_slots: {
    title: { x: 160, y: 40, width: 760, height: 100, font_size: 48, align: 'center' },
    episode_number: { x: 900, y: 48, width: 120, height: 52, font_size: 26, align: 'right' },
  },
});

const document = CanvasDocumentV1Schema.parse(canvasFixture);
const imageVersionId = document.pages[0].panels[0].elements.find((element) => element.type === 'image')?.type === 'image'
  ? document.pages[0].panels[0].elements.find((element) => element.type === 'image')!.asset_version_id
  : '';
const nativeImage = window.Image;

class LoadedImage {
  complete = false;
  naturalWidth = 2;
  naturalHeight = 2;
  crossOrigin: string | null = null;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  set src(_source: string) {
    this.complete = true;
    queueMicrotask(() => this.onload?.());
  }
}

describe('renderPageToPng', () => {
  beforeEach(() => {
    window.Image = LoadedImage as unknown as typeof window.Image;
  });

  afterEach(() => {
    window.Image = nativeImage;
    exportRenderer.pages = [];
    exportRenderer.brand = null;
    exportRenderer.stage = null;
  });

  it('renders the selected page at its original dimensions with the frozen brand shell', async () => {
    const blob = await renderPageToPng(document, document.pages[0].id, {
      brand,
      assetSources: { [imageVersionId]: 'blob:approved-panel-image' },
    });

    expect(blob.type).toBe('image/png');
    expect(exportRenderer.pages[0]).toMatchObject({ width: 1080, height: 1440 });
    expect(exportRenderer.brand).toBe(brand);
    expect(exportRenderer.stage).toMatchObject({ width: expect.any(Function), height: expect.any(Function) });
    expect((exportRenderer.stage as { toDataURL: ReturnType<typeof vi.fn> }).toDataURL)
      .toHaveBeenCalledWith({ pixelRatio: 1, mimeType: 'image/png' });
  });

  it('renders every page in order when exporting an episode', async () => {
    const first = { ...document.pages[0], id: '00000000-0000-4000-8000-000000000101', order: 1 };
    const second = { ...document.pages[0], id: '00000000-0000-4000-8000-000000000102', order: 2 };
    const twoPages = CanvasDocumentV1Schema.parse({ ...document, pages: [second, first] });
    const pages = await renderEpisodePagesToPng(twoPages, {
      brand,
      assetSources: { [imageVersionId]: 'blob:approved-panel-image' },
    });

    expect(pages).toHaveLength(2);
    expect(exportRenderer.pages.map((page) => (page as { id: string }).id)).toEqual([first.id, second.id]);
  });

  it('rejects a page ID outside the document', async () => {
    await expect(renderPageToPng(document, 'missing-page', { brand, assetSources: {} }))
      .rejects.toThrow(/page/i);
  });

  it('does not export a missing approved image as an empty placeholder', async () => {
    await expect(renderPageToPng(document, document.pages[0].id, { brand, assetSources: {} }))
      .rejects.toThrow(/素材/);
  });
});
