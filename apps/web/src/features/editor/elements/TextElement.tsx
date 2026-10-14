import { Text } from 'react-konva';
import type { CanvasElementV1 } from '@ip-studio/contracts/canvas';

export type TextCanvasElement = Extract<CanvasElementV1, { type: 'text' }>;

export function TextElement({ element }: { element: TextCanvasElement }) {
  return (
    <Text
      width={element.transform.width}
      height={element.transform.height}
      text={element.props.text}
      fontFamily={element.props.font_family}
      fontSize={element.props.font_size}
      fontStyle={element.props.font_weight >= 600 ? 'bold' : 'normal'}
      fill={element.props.color}
      align={element.props.align}
      lineHeight={element.props.line_height}
      letterSpacing={element.props.letter_spacing}
      listening={false}
    />
  );
}
