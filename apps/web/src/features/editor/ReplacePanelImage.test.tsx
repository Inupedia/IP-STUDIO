import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import type { CanvasElementV1 } from '@ip-studio/contracts/canvas';
import type { AssetVersion } from '@ip-studio/contracts/domain';
import fixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import { applyCanvasCommand } from './commands';
import { replacePanelImage, ReplacePanelImage } from './ReplacePanelImage';

const original = CanvasDocumentV1Schema.parse(fixture);
const panel = original.pages[0].panels[0];
function getFixtureImage(): Extract<CanvasElementV1, { type: 'image' }> {
  const image = panel.elements.find((element) => element.type === 'image');
  if (!image || image.type !== 'image') throw new Error('Expected image layer in canvas fixture');
  return image;
}
const image = getFixtureImage();
const targetAssetVersionId = '00000000-0000-4000-8000-000000000099';

const availableAssets = [{
  asset_id: '00000000-0000-4000-8000-000000000098',
  asset_version_id: targetAssetVersionId,
  workspace_id: '00000000-0000-4000-8000-000000000097',
  owner_ip_id: '00000000-0000-4000-8000-000000000096',
  type: 'composite_panel',
  name: '审核通过的画格',
  status: 'approved',
  version_no: 2,
  sha256: 'a'.repeat(64),
  mime: 'image/png',
  byte_size: 10,
  width: 3,
  height: 2,
  alpha: true,
  created_at: '2026-10-14T00:00:00Z',
}] as AssetVersion[];

function unlockedDocument() {
  return CanvasDocumentV1Schema.parse({
    ...original,
    pages: original.pages.map((page) => ({
      ...page,
      panels: page.panels.map((candidatePanel) => ({
        ...candidatePanel,
        elements: candidatePanel.elements.map((element) => element.id === image.id
          ? { ...element, locked: false }
          : element),
      })),
    })),
  });
}

function imageVersion(document: typeof original) {
  const target = document.pages.flatMap((page) => page.panels)
    .flatMap((candidatePanel) => candidatePanel.elements)
    .find((element) => element.id === image.id);
  if (!target || target.type !== 'image') throw new Error('Expected image layer');
  return target.asset_version_id;
}

describe('ReplacePanelImage', () => {
  afterEach(cleanup);

  it('replaces only the selected image layer and preserves brand, title and chat text', () => {
    const document = unlockedDocument();
    const onReplace = vi.fn();
    render(
      <ReplacePanelImage
        document={document}
        panelId={panel.id}
        imageElementId={image.id}
        currentAssetVersionId={image.asset_version_id}
        availableAssets={availableAssets}
        onReplace={onReplace}
      />,
    );

    fireEvent.change(screen.getByLabelText('替换单格图片'), { target: { value: targetAssetVersionId } });

    expect(onReplace).toHaveBeenCalledWith({
      type: 'replace_image',
      element_id: image.id,
      asset_version_id: targetAssetVersionId,
    });
    const command = onReplace.mock.calls[0][0];
    const updated = applyCanvasCommand(document, command);
    expect(imageVersion(updated)).toBe(targetAssetVersionId);
    expect(updated.brand_template_version_id).toBe(document.brand_template_version_id);
    expect(updated.dynamic_fields).toEqual(document.dynamic_fields);
    const originalChat = document.pages[0].panels[0].elements.find((element) => element.type === 'chat_message');
    const updatedChat = updated.pages[0].panels[0].elements.find((element) => element.type === 'chat_message');
    expect(updatedChat).toEqual(originalChat);
  });

  it('rejects a panel without a matching unlocked image layer', () => {
    expect(() => replacePanelImage(original, panel.id, targetAssetVersionId, image.id)).toThrow(/locked/i);
    expect(() => replacePanelImage(original, '00000000-0000-4000-8000-000000000099', targetAssetVersionId)).toThrow(/panel/i);
  });
});
