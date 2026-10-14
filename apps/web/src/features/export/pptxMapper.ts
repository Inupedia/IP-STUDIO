import type { CanvasElementV1 } from '@ip-studio/contracts/canvas';
import { resolveMessageSide } from '@ip-studio/contracts/canvas';

export type PptxShapeName = 'rect' | 'roundRect' | 'ellipse' | 'line' | 'triangle' | 'cloud';

interface PositionedObject {
  objectName: string;
  x: number;
  y: number;
  w: number;
  h: number;
  rotate: number;
  opacity: number;
}

export interface PptxShapeObject extends PositionedObject {
  kind: 'shape';
  shape: PptxShapeName;
  fill: string | null;
  stroke: string | null;
  lineWidth: number;
  endArrow?: boolean;
}

export interface PptxTextObject extends PositionedObject {
  kind: 'text';
  text: string;
  fontFace: string;
  fontSize: number;
  bold: boolean;
  color: string;
  align: 'left' | 'center' | 'right';
  lineSpacingMultiple: number;
}

export interface PptxImageObject extends PositionedObject {
  kind: 'image';
  assetVersionId: string;
  data: string;
  crop?: { x: number; y: number; width: number; height: number };
}

export type PptxObject = PptxShapeObject | PptxTextObject | PptxImageObject;

export interface PptxContext {
  pixelsToInches: number;
  offsetX: number;
  offsetY: number;
  assetSources: Record<string, string>;
  warnings: string[];
}

function colorValue(value: string, fallback: string, warnings: string[], elementId: string): string {
  const normalized = value.replace(/^#/, '');
  if (/^[0-9a-f]{6}$/i.test(normalized)) return normalized.toUpperCase();
  if (/^[0-9a-f]{3}$/i.test(normalized)) {
    return normalized.split('').map((channel) => channel + channel).join('').toUpperCase();
  }
  warnings.push(`元素 ${elementId} 的颜色格式不受 PPTX 支持，已使用近似颜色。`);
  return fallback.replace(/^#/, '').toUpperCase();
}

function positioned(
  id: string,
  suffix: string,
  x: number,
  y: number,
  width: number,
  height: number,
  rotation: number,
  opacity: number,
  context: PptxContext,
): PositionedObject {
  const safeId = id.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 40);
  return {
    objectName: `ipstudio-${safeId}-${suffix}`,
    x: context.offsetX + x * context.pixelsToInches,
    y: context.offsetY + y * context.pixelsToInches,
    w: width * context.pixelsToInches,
    h: height * context.pixelsToInches,
    rotate: rotation,
    opacity,
  };
}

function shape(
  id: string,
  suffix: string,
  name: PptxShapeName,
  x: number,
  y: number,
  width: number,
  height: number,
  fill: string | null,
  stroke: string | null,
  strokeWidth: number,
  rotation: number,
  opacity: number,
  context: PptxContext,
  endArrow = false,
): PptxShapeObject {
  return {
    kind: 'shape',
    shape: name,
    ...positioned(id, suffix, x, y, width, height, rotation, opacity, context),
    fill: fill ? colorValue(fill, '#FFFFFF', context.warnings, id) : null,
    stroke: stroke ? colorValue(stroke, '#242923', context.warnings, id) : null,
    lineWidth: strokeWidth * context.pixelsToInches * 72,
    endArrow,
  };
}

function textObject(
  id: string,
  suffix: string,
  text: string,
  x: number,
  y: number,
  width: number,
  height: number,
  fontFace: string,
  fontSizePx: number,
  color: string,
  align: 'left' | 'center' | 'right',
  lineSpacingMultiple: number,
  rotation: number,
  opacity: number,
  context: PptxContext,
): PptxTextObject {
  return {
    kind: 'text',
    ...positioned(id, suffix, x, y, width, height, rotation, opacity, context),
    text,
    fontFace,
    fontSize: fontSizePx * context.pixelsToInches * 72,
    bold: false,
    color: colorValue(color, '#242923', context.warnings, id),
    align,
    lineSpacingMultiple,
  };
}

function warnWhenTextMayOverflow(
  id: string,
  value: string,
  fontSize: number,
  lineHeight: number,
  width: number,
  height: number,
  warnings: string[],
): void {
  const lines = value.split('\n');
  const estimatedLineCount = lines.reduce((total, line) => {
    const estimatedWidth = [...line].reduce((sum, character) => {
      if (/\s/.test(character)) return sum + fontSize * 0.3;
      return sum + fontSize * (/^[\u0000-\u00ff]$/.test(character) ? 0.55 : 1);
    }, 0);
    return total + Math.max(1, Math.ceil(estimatedWidth / Math.max(width, 1)));
  }, 0);
  if (estimatedLineCount * fontSize * lineHeight > height) {
    warnings.push(`元素 ${id} 的文字可能超出文本框；请在 PowerPoint 中检查换行。`);
  }
}

function imageObject(
  element: Extract<CanvasElementV1, { type: 'image' | 'sticker' }>,
  context: PptxContext,
  originX: number,
  originY: number,
): PptxImageObject | null {
  const source = context.assetSources[element.asset_version_id];
  if (!source) {
    context.warnings.push(`缺少素材 ${element.asset_version_id}，该图片没有加入 PPTX。`);
    return null;
  }
  if (element.type === 'image' && (
    element.crop.x !== 0 || element.crop.y !== 0 || element.crop.width !== 1 || element.crop.height !== 1
  )) {
    context.warnings.push(`元素 ${element.id} 的图片裁切会写入位图对象；后续请从工程 ZIP 调整裁切。`);
  }
  return {
    kind: 'image',
    ...positioned(
      element.id, 'image', originX + element.transform.x, originY + element.transform.y,
      element.transform.width, element.transform.height, element.transform.rotation,
      element.opacity, context,
    ),
    assetVersionId: element.asset_version_id,
    data: source,
    crop: element.type === 'image' ? element.crop : undefined,
  };
}

function mapBubble(
  element: Extract<CanvasElementV1, { type: 'speech_bubble' | 'thought_bubble' }>,
  context: PptxContext,
  originX: number,
  originY: number,
): PptxObject[] {
  const { x, y, width, height, rotation } = element.transform;
  const { fill, stroke, stroke_width: strokeWidth, tail_position: tailPosition } = element.props;
  const mainShape: PptxShapeName = element.type === 'thought_bubble'
    ? (element.props.shape === 'cloud' ? 'cloud' : 'ellipse')
    : element.props.shape === 'ellipse'
      ? 'ellipse'
      : element.props.shape === 'cloud'
        ? 'cloud'
        : 'roundRect';
  const objects: PptxObject[] = [];
  const tailSize = Math.max(18, Math.min(width, height) * 0.18);
  if (tailPosition !== 'none') {
    if (element.type === 'thought_bubble') {
      const alongX = tailPosition === 'left' || tailPosition === 'right';
      const first = positioned(
        element.id, 'thought-tail-small',
        originX + x + (alongX ? (tailPosition === 'left' ? 0 : width - tailSize) : width * 0.7),
        originY + y + (alongX ? height * 0.76 : (tailPosition === 'top' ? 0 : height - tailSize)),
        tailSize * 0.4, tailSize * 0.4, rotation, element.opacity, context,
      );
      const second = positioned(
        element.id, 'thought-tail-large',
        originX + x + (alongX ? (tailPosition === 'left' ? tailSize * 0.35 : width - tailSize * 1.25) : width * 0.7 - tailSize * 0.35),
        originY + y + (alongX ? height * 0.65 : (tailPosition === 'top' ? tailSize * 0.35 : height - tailSize * 1.25)),
        tailSize * 0.65, tailSize * 0.65, rotation, element.opacity, context,
      );
      objects.push(
        { kind: 'shape', shape: 'ellipse', ...first, fill: colorValue(fill, '#FFFFFF', context.warnings, element.id), stroke: null, lineWidth: 0 },
        { kind: 'shape', shape: 'ellipse', ...second, fill: colorValue(fill, '#FFFFFF', context.warnings, element.id), stroke: null, lineWidth: 0 },
      );
      context.warnings.push(`元素 ${element.id} 的思考气泡尾部使用独立圆点近似。`);
    } else {
      let tailX = originX + x + width * 0.65 - tailSize / 2;
      let tailY = originY + y + height - tailSize * 0.48;
      let tailRotation = 180;
      if (tailPosition === 'top') {
        tailY = originY + y - tailSize * 0.52;
        tailRotation = 0;
      } else if (tailPosition === 'left') {
        tailX = originX + x - tailSize * 0.52;
        tailY = originY + y + height * 0.62 - tailSize / 2;
        tailRotation = 270;
      } else if (tailPosition === 'right') {
        tailX = originX + x + width - tailSize * 0.48;
        tailY = originY + y + height * 0.62 - tailSize / 2;
        tailRotation = 90;
      }
      objects.push(shape(
        element.id, 'speech-tail', 'triangle', tailX, tailY, tailSize, tailSize,
        fill, stroke, strokeWidth, tailRotation + rotation, element.opacity, context,
      ));
      context.warnings.push(`元素 ${element.id} 的对话气泡尾巴使用独立三角形近似。`);
    }
  }
  objects.push(shape(
    element.id, 'bubble', mainShape, originX + x, originY + y, width, height,
    fill, stroke, strokeWidth, rotation, element.opacity, context,
  ));
  const textX = originX + x + 12;
  const textY = originY + y + 10;
  const textWidth = Math.max(1, width - 24);
  const textHeight = Math.max(1, height - 20);
  warnWhenTextMayOverflow(element.id, element.props.text, element.props.font_size, 1.2, textWidth, textHeight, context.warnings);
  objects.push(textObject(
    element.id, 'bubble-text', element.props.text, textX, textY, textWidth, textHeight,
    element.props.font_family, element.props.font_size, '#242923', 'center', 1.2,
    rotation, element.opacity, context,
  ));
  return objects;
}

export function mapCanvasElementToPptx(element: CanvasElementV1, context: PptxContext): PptxObject[] {
  const { transform, opacity } = element;
  const originX = 0;
  const originY = 0;
  const x = transform.x;
  const y = transform.y;
  if (element.type === 'image' || element.type === 'sticker') {
    const mapped = imageObject(element, context, originX, originY);
    return mapped ? [mapped] : [];
  }
  if (element.type === 'text') {
    warnWhenTextMayOverflow(element.id, element.props.text, element.props.font_size,
      element.props.line_height, transform.width, transform.height, context.warnings);
    const mapped = textObject(
      element.id, 'text', element.props.text, x, y, transform.width, transform.height,
      element.props.font_family, element.props.font_size, element.props.color, element.props.align,
      element.props.line_height, transform.rotation, opacity, context,
    );
    mapped.bold = element.props.font_weight >= 600;
    return [mapped];
  }
  if (element.type === 'speech_bubble' || element.type === 'thought_bubble') {
    return mapBubble(element, context, originX, originY);
  }
  if (element.type === 'chat_message') {
    const derivedSide = resolveMessageSide(element.props.sender_id, element.props.self_participant_id);
    const side = element.props.direction_override ?? derivedSide;
    if (element.props.direction_override && element.props.direction_override !== derivedSide) {
      context.warnings.push(`元素 ${element.id} 的手动方向覆盖了发送者推导方向。`);
    }
    const bubbleWidth = transform.width * 0.86;
    const bubbleX = side === 'right' ? x + transform.width - bubbleWidth : x;
    const textInset = 13;
    const messageHeight = Math.max(1, transform.height - 42);
    warnWhenTextMayOverflow(element.id, element.props.text, 24, 1.2,
      bubbleWidth - textInset * 2, messageHeight, context.warnings);
    const dark = element.props.theme === 'dark';
    const background = dark ? (side === 'right' ? '#637d69' : '#444a45')
      : (side === 'right' ? '#dcebd9' : '#ffffff');
    const foreground = dark ? '#ffffff' : '#242923';
    const muted = dark ? '#e0e2de' : '#73796f';
    return [
      shape(element.id, 'message-bubble', 'roundRect', bubbleX, y, bubbleWidth, transform.height,
        background, '#d8dcd3', 1, transform.rotation, opacity, context),
      textObject(element.id, 'message-text', element.props.text, bubbleX + textInset, y + 12,
        bubbleWidth - textInset * 2, messageHeight, 'sans-serif', 24, foreground, 'left', 1.2,
        transform.rotation, opacity, context),
      textObject(element.id, 'message-time', element.props.sent_at, bubbleX + textInset,
        y + transform.height - 26, bubbleWidth - textInset * 2, 16, 'sans-serif', 11, muted,
        side === 'right' ? 'right' : 'left', 1, transform.rotation, opacity, context),
    ];
  }

  if (element.type === 'shape') {
    const props = element.props;
    let shapeName: PptxShapeName = 'rect';
    let endArrow = false;
    if (props.shape === 'ellipse') shapeName = 'ellipse';
    else if (props.shape === 'rounded_rectangle') shapeName = 'roundRect';
    else if (props.shape === 'line' || props.shape === 'arrow') {
      shapeName = 'line';
      endArrow = props.shape === 'arrow';
    }
    return [shape(
      element.id, element.type, shapeName, x, y, transform.width, transform.height,
      props.fill, props.stroke, props.stroke_width, transform.rotation, opacity, context, endArrow,
    )];
  }
  if (element.type === 'panel_frame') {
    return [shape(
      element.id, element.type, 'rect', x, y, transform.width, transform.height,
      element.props.fill, element.props.stroke, element.props.stroke_width,
      transform.rotation, opacity, context,
    )];
  }
  return [];
}
