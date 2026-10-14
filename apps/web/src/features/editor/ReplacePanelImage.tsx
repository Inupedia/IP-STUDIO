import { useState } from 'react';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import type { AssetVersion } from '@ip-studio/contracts/domain';
import type { CanvasCommand } from './commands';

export interface ReplacePanelImageProps {
  document: CanvasDocumentV1;
  panelId: string;
  imageElementId: string;
  currentAssetVersionId: string;
  availableAssets: AssetVersion[];
  onReplace: (command: CanvasCommand) => void;
}

export function replacePanelImage(
  document: CanvasDocumentV1,
  panelId: string,
  assetVersionId: string,
  imageElementId?: string,
): CanvasCommand {
  const panels = document.pages.flatMap((page) => page.panels)
    .filter((panel) => panel.id === panelId);
  if (panels.length !== 1) throw new Error(`Canvas panel ${panelId} is missing or ambiguous`);

  const images = panels[0].elements.filter((element) =>
    (element.type === 'image' || element.type === 'sticker') && !element.locked,
  );
  let target = imageElementId
    ? panels[0].elements.find((element) => element.id === imageElementId)
    : images.length === 1 ? images[0] : undefined;
  if (!target || (target.type !== 'image' && target.type !== 'sticker')) {
    throw new Error('Select an image layer in this panel before replacing its image');
  }
  if (target.locked) throw new Error('The selected image layer is locked');
  if (!images.some((image) => image.id === target.id)) {
    throw new Error('The selected image layer does not belong to this panel');
  }
  return { type: 'replace_image', element_id: target.id, asset_version_id: assetVersionId };
}

export function ReplacePanelImage({
  document,
  panelId,
  imageElementId,
  currentAssetVersionId,
  availableAssets,
  onReplace,
}: ReplacePanelImageProps) {
  const [error, setError] = useState('');
  const approvedAssets = availableAssets.filter((asset) =>
    asset.status === 'approved' && asset.asset_version_id !== currentAssetVersionId,
  );

  return (
    <label className="replace-panel-image">
      <span>替换素材</span>
      <select
        aria-label="替换单格图片"
        value={currentAssetVersionId}
        onChange={(event) => {
          const assetVersionId = event.currentTarget.value;
          if (assetVersionId === currentAssetVersionId) return;
          try {
            const command = replacePanelImage(document, panelId, assetVersionId, imageElementId);
            onReplace(command);
            setError('');
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : '无法替换画格图片');
          }
        }}
      >
        <option value={currentAssetVersionId}>当前素材</option>
        {approvedAssets.map((asset) => (
          <option key={asset.asset_version_id} value={asset.asset_version_id}>
            {asset.name} · v{asset.version_no}
          </option>
        ))}
      </select>
      {error && <span className="form-error" role="alert">{error}</span>}
    </label>
  );
}
