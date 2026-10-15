import { useEffect, useState } from 'react';
import Konva from 'konva';
import {
  Arrow,
  Ellipse,
  Group,
  Image as KonvaImage,
  Layer,
  Line,
  Rect,
  Text,
} from 'react-konva';
import type { CanvasDocumentV1, CanvasElementV1 } from '@ip-studio/contracts/canvas';
import { ChatMessage } from './elements/ChatMessage';
import { TextElement } from './elements/TextElement';

type ElementTransform = CanvasElementV1['transform'];

function useImage(source: string | undefined): HTMLImageElement | undefined {
  const [image, setImage] = useState<HTMLImageElement>();
  useEffect(() => {
    if (!source) {
      setImage(undefined);
      return;
    }
    const loadedImage = new window.Image();
    loadedImage.crossOrigin = 'anonymous';
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

interface ElementNodeProps {
  element: CanvasElementV1;
  assetSources: Record<string, string>;
  onSelect: (id: string, additive?: boolean) => void;
  onEditText: (id: string) => void;
  onDragStart: (id: string) => void;
  onPositionChange: (id: string, transform: ElementTransform) => void;
}

function ElementHitTarget({ width, height }: { width: number; height: number }) {
  return <Rect width={width} height={height} fill="transparent" />;
}

function ElementNode({ element, assetSources, onSelect, onEditText, onDragStart, onPositionChange }: ElementNodeProps) {
  const assetVersionId = 'asset_version_id' in element ? element.asset_version_id : undefined;
  const image = useImage(assetVersionId ? assetSources[assetVersionId] : undefined);
  const transform = element.transform;
  const draggable = !element.locked;
  const handleDragEnd = (event: Konva.KonvaEventObject<DragEvent>) => {
    onPositionChange(element.id, { ...transform, x: event.target.x(), y: event.target.y() });
  };
  const groupProps = {
    id: element.id,
    x: transform.x,
    y: transform.y,
    width: transform.width,
    height: transform.height,
    rotation: transform.rotation,
    opacity: element.opacity,
    draggable,
    listening: true,
    onClick: (event: Konva.KonvaEventObject<MouseEvent>) => onSelect(
      element.id,
      event.evt.shiftKey || event.evt.metaKey || event.evt.ctrlKey,
    ),
    onTap: () => onSelect(element.id),
    onDragStart: () => onDragStart(element.id),
    onDblClick: !element.locked && ['text', 'chat_message', 'speech_bubble', 'thought_bubble'].includes(element.type)
      ? () => onEditText(element.id)
      : undefined,
    onDragEnd: handleDragEnd,
  };

  switch (element.type) {
    case 'image':
    case 'sticker':
      return (
        <Group {...groupProps}>
          <ElementHitTarget width={transform.width} height={transform.height} />
          {image ? (
            <KonvaImage image={image} width={transform.width} height={transform.height} crop={{
              x: element.type === 'image' ? element.crop.x * image.width : 0,
              y: element.type === 'image' ? element.crop.y * image.height : 0,
              width: element.type === 'image' ? element.crop.width * image.width : image.width,
              height: element.type === 'image' ? element.crop.height * image.height : image.height,
            }} opacity={element.opacity} listening={false} />
          ) : (
            <Rect width={transform.width} height={transform.height} fill="#eeeeea" stroke="#a9ada4" dash={[6, 4]} listening={false} />
          )}
        </Group>
      );
    case 'text':
      return (
        <Group {...groupProps}>
          <ElementHitTarget width={transform.width} height={transform.height} />
          <TextElement element={element} />
        </Group>
      );
    case 'speech_bubble':
    case 'thought_bubble':
      return (
        <Group {...groupProps}>
          <ElementHitTarget width={transform.width} height={transform.height} />
          <Rect
            width={transform.width}
            height={transform.height}
            cornerRadius={element.props.shape === 'ellipse' ? transform.height / 2 : 18}
            fill={element.props.fill}
            stroke={element.props.stroke}
            strokeWidth={element.props.stroke_width}
            listening={false}
          />
          <Text
            x={12}
            y={10}
            width={Math.max(1, transform.width - 24)}
            height={Math.max(1, transform.height - 20)}
            text={element.props.text}
            fontFamily={element.props.font_family}
            fontSize={element.props.font_size}
            fill="#242923"
            align="center"
            verticalAlign="middle"
            listening={false}
          />
        </Group>
      );
    case 'chat_message': {
      return (
        <Group {...groupProps}>
          <ElementHitTarget width={transform.width} height={transform.height} />
          <ChatMessage element={element} />
        </Group>
      );
    }
    case 'shape':
      if (element.props.shape === 'ellipse') {
        return (
          <Group {...groupProps}>
            <ElementHitTarget width={transform.width} height={transform.height} />
            <Ellipse
              x={transform.width / 2}
              y={transform.height / 2}
              radiusX={transform.width / 2}
              radiusY={transform.height / 2}
              fill={element.props.fill ?? 'transparent'}
              stroke={element.props.stroke}
              strokeWidth={element.props.stroke_width}
              listening={false}
            />
          </Group>
        );
      }
      if (element.props.shape === 'line' || element.props.shape === 'arrow') {
        const ShapeComponent = element.props.shape === 'arrow' ? Arrow : Line;
        return (
          <Group {...groupProps}>
            <ElementHitTarget width={transform.width} height={transform.height} />
            <ShapeComponent
              points={[0, 0, transform.width, transform.height]}
              stroke={element.props.stroke}
              strokeWidth={element.props.stroke_width}
              fill={element.props.fill ?? undefined}
              listening={false}
            />
          </Group>
        );
      }
      return (
        <Group {...groupProps}>
          <ElementHitTarget width={transform.width} height={transform.height} />
          <Rect
            width={transform.width}
            height={transform.height}
            cornerRadius={element.props.shape === 'rounded_rectangle' ? 12 : 0}
            fill={element.props.fill ?? 'transparent'}
            stroke={element.props.stroke}
            strokeWidth={element.props.stroke_width}
            listening={false}
          />
        </Group>
      );
    case 'panel_frame':
      return (
        <Group {...groupProps}>
          <ElementHitTarget width={transform.width} height={transform.height} />
          <Rect
            width={transform.width}
            height={transform.height}
            fill={element.props.fill ?? 'transparent'}
            stroke={element.props.stroke}
            strokeWidth={element.props.stroke_width}
            listening={false}
          />
        </Group>
      );
  }
}

export function PanelLayer({
  page,
  assetSources,
  onSelect,
  onEditText,
  onDragStart,
  onPositionChange,
}: {
  page: CanvasDocumentV1['pages'][number];
  assetSources: Record<string, string>;
  onSelect: (id: string, additive?: boolean) => void;
  onEditText: (id: string) => void;
  onDragStart: (id: string) => void;
  onPositionChange: (id: string, transform: ElementTransform) => void;
}) {
  return (
    <Layer id="panel-content-layer">
      {page.panels.map((panel) => (
        <Group
          key={panel.id}
          id={`panel-${panel.id}`}
          x={panel.rect.x}
          y={panel.rect.y}
          clipX={0}
          clipY={0}
          clipWidth={panel.rect.width}
          clipHeight={panel.rect.height}
        >
          <Rect
            width={panel.rect.width}
            height={panel.rect.height}
            fill="#fffefa"
            stroke="#4d514a"
            strokeWidth={2}
            listening={false}
          />
          {[...panel.elements].sort((first, second) => first.z_index - second.z_index).map((element) => (
            <ElementNode
              key={element.id}
              element={element}
              assetSources={assetSources}
              onSelect={onSelect}
              onEditText={onEditText}
              onDragStart={onDragStart}
              onPositionChange={onPositionChange}
            />
          ))}
        </Group>
      ))}
    </Layer>
  );
}
