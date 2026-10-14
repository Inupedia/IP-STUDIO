import { Group, Rect, Text } from 'react-konva';
import type { CanvasElementV1 } from '@ip-studio/contracts/canvas';
import { resolveMessageSide } from '@ip-studio/contracts/canvas';

export type ChatMessageCanvasElement = Extract<CanvasElementV1, { type: 'chat_message' }>;

export function ChatMessage({ element }: { element: ChatMessageCanvasElement }) {
  const { transform, props } = element;
  const side = props.direction_override ?? resolveMessageSide(props.sender_id, props.self_participant_id);
  const bubbleWidth = transform.width * 0.86;
  const bubbleX = side === 'right' ? transform.width - bubbleWidth : 0;
  const fill = props.theme === 'dark'
    ? (side === 'right' ? '#637d69' : '#444a45')
    : (side === 'right' ? '#dcebd9' : '#ffffff');

  return (
    <Group>
      <Rect
        x={bubbleX}
        width={bubbleWidth}
        height={transform.height}
        cornerRadius={17}
        fill={fill}
        stroke="#d8dcd3"
        strokeWidth={1}
        listening={false}
      />
      <Text
        x={bubbleX + 13}
        y={12}
        width={bubbleWidth - 26}
        height={transform.height - 42}
        text={props.text}
        fontSize={24}
        fill={props.theme === 'dark' ? '#fff' : '#242923'}
        listening={false}
      />
      <Text
        x={bubbleX + 13}
        y={transform.height - 26}
        width={bubbleWidth - 26}
        height={16}
        text={props.sent_at}
        fontSize={11}
        fill={props.theme === 'dark' ? '#e0e2de' : '#73796f'}
        align={side === 'right' ? 'right' : 'left'}
        listening={false}
      />
    </Group>
  );
}
