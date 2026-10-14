import { describe, expect, it } from 'vitest';
import type { CanvasElementV1 } from '@ip-studio/contracts/canvas';
import { mapCanvasElementToPptx } from './pptxMapper';

const selfId = '10000000-0000-4000-8000-000000000001';
const friendId = '10000000-0000-4000-8000-000000000002';
const assetVersionId = '10000000-0000-4000-8000-000000000003';

function context() {
  return {
    pixelsToInches: 1 / 96,
    offsetX: 1,
    offsetY: 2,
    assetSources: { [assetVersionId]: 'data:image/png;base64,AAAA' },
    warnings: [] as string[],
  };
}

function chatMessage(senderId: string, directionOverride?: 'left' | 'right' | null): CanvasElementV1 {
  return {
    id: '10000000-0000-4000-8000-000000000010',
    type: 'chat_message',
    props: {
      self_participant_id: selfId,
      sender_id: senderId,
      text: senderId === selfId ? '不在。' : '在吗？',
      sent_at: '22:17',
      theme: 'light',
      direction_override: directionOverride,
    },
    transform: { x: 120, y: 80, width: 400, height: 150, rotation: 0 },
    opacity: 1,
    z_index: 1,
    locked: false,
  };
}

describe('mapCanvasElementToPptx', () => {
  it('maps text to a native PowerPoint text object in page coordinates', () => {
    const element: CanvasElementV1 = {
      id: '10000000-0000-4000-8000-000000000011',
      type: 'text',
      props: {
        text: '单独编辑的中文', font_family: 'Noto Sans CJK SC', font_size: 32,
        font_weight: 700, color: '#243a2d', align: 'center', line_height: 1.3,
        letter_spacing: 0,
      },
      transform: { x: 96, y: 192, width: 480, height: 100, rotation: 12 },
      opacity: 1,
      z_index: 2,
      locked: false,
    };

    const objects = mapCanvasElementToPptx(element, context());

    expect(objects).toHaveLength(1);
    expect(objects[0]).toMatchObject({
      kind: 'text', text: '单独编辑的中文', x: 2, y: 4, w: 5,
      fontSize: 24, bold: true, rotate: 12,
    });
    expect(objects[0].h).toBeCloseTo(100 / 96, 10);
  });

  it('keeps friend and self chat bubbles on the correct sides with separate text objects', () => {
    const friend = mapCanvasElementToPptx(chatMessage(friendId), context());
    const self = mapCanvasElementToPptx(chatMessage(selfId), context());

    expect(friend.find((object) => object.kind === 'shape')?.x).toBeCloseTo(2.25, 3);
    expect(friend.find((object) => object.kind === 'shape')?.w).toBeCloseTo(3.583, 3);
    expect(friend.filter((object) => object.kind === 'text').map((object) => object.text)).toEqual(['在吗？', '22:17']);
    expect(self.find((object) => object.kind === 'shape')?.x).toBeCloseTo(2.833, 3);
    expect(self.find((object) => object.kind === 'shape')?.w).toBeCloseTo(3.583, 3);
    expect(self.filter((object) => object.kind === 'text').map((object) => object.text)).toEqual(['不在。', '22:17']);
  });

  it('keeps a speech bubble body, tail, and Chinese copy as separate native objects', () => {
    const element: CanvasElementV1 = {
      id: '10000000-0000-4000-8000-000000000012',
      type: 'speech_bubble',
      props: {
        text: '你好', shape: 'rounded_rectangle', fill: '#ffffff', stroke: '#242923',
        stroke_width: 2, tail_position: 'bottom', font_family: 'sans-serif', font_size: 28,
      },
      transform: { x: 100, y: 200, width: 320, height: 160, rotation: 0 },
      opacity: 1,
      z_index: 3,
      locked: false,
    };

    const objects = mapCanvasElementToPptx(element, context());

    expect(objects.filter((object) => object.kind === 'shape')).toHaveLength(2);
    expect(objects.find((object) => object.kind === 'text')).toMatchObject({ text: '你好' });
  });

  it('warns when a manual chat direction overrides sender-derived placement', () => {
    const warnings: string[] = [];
    const objects = mapCanvasElementToPptx(chatMessage(friendId, 'right'), { ...context(), warnings });

    expect(objects.find((object) => object.kind === 'shape')?.x).toBeCloseTo(2.833, 3);
    expect(warnings.some((warning) => warning.includes('方向覆盖'))).toBe(true);
  });
});
