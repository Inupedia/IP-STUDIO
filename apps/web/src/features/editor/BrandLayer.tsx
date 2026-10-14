import { useEffect, useState } from 'react';
import { Image as KonvaImage, Layer, Rect, Text } from 'react-konva';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';

type Placement = 'background' | 'foreground';

function useImage(source: string | undefined): HTMLImageElement | undefined {
  const [image, setImage] = useState<HTMLImageElement>();
  useEffect(() => {
    if (!source) {
      setImage(undefined);
      return;
    }
    const loadedImage = new window.Image();
    loadedImage.onload = () => setImage(loadedImage);
    loadedImage.onerror = () => setImage(undefined);
    loadedImage.src = source;
    return () => {
      loadedImage.onload = null;
      loadedImage.onerror = null;
    };
  }, [source]);
  return image;
}

function LockedElement({
  element,
  assetSources,
}: {
  element: BrandTemplateV1['locked_elements'][number];
  assetSources: Record<string, string>;
}) {
  const image = useImage(element.asset_version_id ? assetSources[element.asset_version_id] : undefined);
  const id = `brand-element-${element.id}`;
  if (image) {
    return (
      <KonvaImage
        id={id}
        image={image}
        x={element.x}
        y={element.y}
        width={element.width}
        height={element.height}
        opacity={element.opacity}
        listening={false}
        draggable={false}
      />
    );
  }
  return (
    <Rect
      id={id}
      x={element.x}
      y={element.y}
      width={element.width}
      height={element.height}
      opacity={element.opacity}
      fill={element.fill ?? 'transparent'}
      listening={false}
      draggable={false}
    />
  );
}

export interface BrandLayerProps {
  brand: BrandTemplateV1;
  placement: Placement;
  title: string;
  episodeNumber: string;
  assetSources: Record<string, string>;
}

export function BrandLayer({ brand, placement, title, episodeNumber, assetSources }: BrandLayerProps) {
  if (placement === 'background') {
    return (
      <Layer id="brand-background-layer" listening={false}>
        {brand.locked_elements
          .filter((element) => element.kind === 'background')
          .map((element) => <LockedElement key={element.id} element={element} assetSources={assetSources} />)}
      </Layer>
    );
  }

  const titleSlot = brand.dynamic_slots.title;
  const episodeSlot = brand.dynamic_slots.episode_number;
  return (
    <Layer id="brand-shell-layer" listening={false}>
      {brand.locked_elements
        .filter((element) => element.kind !== 'background')
        .map((element) => <LockedElement key={element.id} element={element} assetSources={assetSources} />)}
      <Text
        id="brand-dynamic-title"
        x={titleSlot.x}
        y={titleSlot.y}
        width={titleSlot.width}
        height={titleSlot.height}
        text={title}
        fontFamily={titleSlot.font_family}
        fontSize={titleSlot.font_size}
        fill={titleSlot.color}
        align={titleSlot.align}
        verticalAlign="middle"
        listening={false}
        draggable={false}
      />
      <Text
        id="brand-dynamic-episode-number"
        x={episodeSlot.x}
        y={episodeSlot.y}
        width={episodeSlot.width}
        height={episodeSlot.height}
        text={episodeNumber}
        fontFamily={episodeSlot.font_family}
        fontSize={episodeSlot.font_size}
        fill={episodeSlot.color}
        align={episodeSlot.align}
        verticalAlign="middle"
        listening={false}
        draggable={false}
      />
    </Layer>
  );
}
