import JSZip from 'jszip';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import { exportEpisodePptx } from './exportPptx';

const assetVersionId = '10000000-0000-4000-8000-000000000003';
const assetPng = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhZkAAAAASUVORK5CYII=';

const document: CanvasDocumentV1 = {
  schema_version: '1.0',
  episode_id: '10000000-0000-4000-8000-000000000004',
  revision: 3,
  style_version_id: null,
  brand_template_version_id: '10000000-0000-4000-8000-000000000005',
  dynamic_fields: { title: '在吗？', episode_number: 'EP.01' },
  pages: [{
    id: '10000000-0000-4000-8000-000000000006',
    width: 1080,
    height: 1440,
    order: 1,
    layout_code: 'custom',
    brand_template_version_id: '10000000-0000-4000-8000-000000000005',
    panels: [{
      id: '10000000-0000-4000-8000-000000000007',
      rect: { x: 48, y: 120, width: 984, height: 620 },
      elements: [
        {
          id: '10000000-0000-4000-8000-000000000008', type: 'image', asset_version_id: assetVersionId,
          transform: { x: 0, y: 0, width: 480, height: 620, rotation: 0 },
          crop: { x: 0, y: 0, width: 1, height: 1 }, opacity: 1, z_index: 1, locked: false,
        },
        {
          id: '10000000-0000-4000-8000-000000000009', type: 'image', asset_version_id: assetVersionId,
          transform: { x: 504, y: 0, width: 480, height: 620, rotation: 0 },
          crop: { x: 0, y: 0, width: 1, height: 1 }, opacity: 1, z_index: 2, locked: false,
        },
        {
          id: '10000000-0000-4000-8000-000000000010', type: 'chat_message',
          props: {
            self_participant_id: '10000000-0000-4000-8000-000000000001',
            sender_id: '10000000-0000-4000-8000-000000000002', text: '在吗？', sent_at: '22:17', theme: 'light',
          },
          transform: { x: 40, y: 80, width: 400, height: 150, rotation: 0 },
          opacity: 1, z_index: 3, locked: false,
        },
        {
          id: '10000000-0000-4000-8000-000000000011', type: 'chat_message',
          props: {
            self_participant_id: '10000000-0000-4000-8000-000000000001',
            sender_id: '10000000-0000-4000-8000-000000000001', text: '不在。', sent_at: '22:19', theme: 'light',
          },
          transform: { x: 544, y: 260, width: 400, height: 150, rotation: 0 },
          opacity: 1, z_index: 4, locked: false,
        },
      ],
    }],
  }],
};

const brand: BrandTemplateV1 = {
  schema_version: '1.0',
  width: 1080,
  height: 1440,
  locked_elements: [
    {
      id: 'background', kind: 'background', locked: true,
      x: 0, y: 0, width: 1080, height: 1440, fill: '#f4f0e8', opacity: 1,
    },
    {
      id: 'logo', kind: 'logo', locked: true,
      x: 48, y: 40, width: 120, height: 60, fill: '#243a2d', opacity: 1,
    },
    {
      id: 'footer', kind: 'footer', locked: true,
      x: 48, y: 1380, width: 984, height: 24, fill: '#eeeeee', opacity: 1,
    },
  ],
  dynamic_slots: {
    title: { x: 160, y: 40, width: 760, height: 100, font_family: 'sans-serif', font_size: 48, color: '#243a2d', align: 'center' },
    episode_number: { x: 900, y: 48, width: 120, height: 52, font_family: 'sans-serif', font_size: 28, color: '#243a2d', align: 'right' },
  },
};

function readBlob(blob: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error('Unable to read PPTX Blob'));
    reader.onload = () => {
      if (reader.result instanceof ArrayBuffer) resolve(reader.result);
      else reject(new Error('PPTX Blob did not return binary data'));
    };
    reader.readAsArrayBuffer(blob);
  });
}

describe('exportEpisodePptx', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('writes independent native text, shapes, frames, and image objects to PPTX XML', async () => {
    const result = await exportEpisodePptx(document, { brand, assetSources: { [assetVersionId]: assetPng } });
    const archive = await JSZip.loadAsync(await readBlob(result.blob));
    const slideXml = await archive.file('ppt/slides/slide1.xml')?.async('string');

    expect(slideXml).toBeTruthy();
    expect((slideXml?.match(/<p:pic\b/g) ?? []).length).toBe(2);
    expect((slideXml?.match(/<p:sp\b/g) ?? []).length).toBeGreaterThan(8);
    expect(slideXml).toContain('在吗？');
    expect(slideXml).toContain('不在。');
    expect(slideXml).toContain('EP.01');
    expect(result.warnings.some((warning) => warning.includes('字体和自动换行'))).toBe(true);
  });

  it('reports when the PPTX has to approximate an image crop', async () => {
    vi.stubGlobal('createImageBitmap', async () => ({
      width: 1,
      height: 1,
      close: vi.fn(),
    }));
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(assetPng);
    const cropped = structuredClone(document);
    const image = cropped.pages[0].panels[0].elements[0];
    if (image.type === 'image') image.crop = { x: 0.2, y: 0.1, width: 0.6, height: 0.7 };

    const result = await exportEpisodePptx(cropped, { brand, assetSources: { [assetVersionId]: assetPng } });

    expect(result.warnings.some((warning) => warning.includes('裁切'))).toBe(true);
  });

  it('fails when a referenced image source is missing instead of exporting a blank placeholder', async () => {
    await expect(exportEpisodePptx(document, { brand, assetSources: {} })).rejects.toThrow('缺少素材');
  });
});
