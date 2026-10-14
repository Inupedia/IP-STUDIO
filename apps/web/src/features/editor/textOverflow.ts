import type { CanvasElementV1 } from '@ip-studio/contracts/canvas';

/**
 * Estimates line wrapping without requiring browser font metrics. CJK glyphs
 * are treated as one em; Latin glyphs use a conservative average width.
 */
export function mayOverflowTextBox(
  text: string,
  fontSize: number,
  lineHeight: number,
  width: number,
  height: number,
  letterSpacing = 0,
): boolean {
  if (width <= 0 || height <= 0 || fontSize <= 0 || lineHeight <= 0) return true;

  const maxWidth = Math.max(1, width);
  let lineCount = 0;
  for (const line of text.split('\n')) {
    let usedWidth = 0;
    let linesForParagraph = 1;
    for (const character of line) {
      const glyphWidth = /[\u2e80-\u9fff\uf900-\ufaff]/u.test(character)
        ? fontSize
        : /\s/u.test(character)
          ? fontSize * 0.32
          : fontSize * 0.56;
      const advance = glyphWidth + letterSpacing;
      if (usedWidth > 0 && usedWidth + advance > maxWidth) {
        linesForParagraph += 1;
        usedWidth = 0;
      }
      usedWidth += advance;
    }
    lineCount += linesForParagraph;
  }

  return lineCount * fontSize * lineHeight > height;
}

export function canvasElementMayOverflowText(element: CanvasElementV1): boolean {
  switch (element.type) {
    case 'text':
      return mayOverflowTextBox(
        element.props.text,
        element.props.font_size,
        element.props.line_height,
        element.transform.width,
        element.transform.height,
        element.props.letter_spacing,
      );
    case 'speech_bubble':
    case 'thought_bubble':
      return mayOverflowTextBox(
        element.props.text,
        element.props.font_size,
        1.2,
        element.transform.width - 24,
        element.transform.height - 20,
      );
    case 'chat_message':
      return mayOverflowTextBox(
        element.props.text,
        24,
        1.2,
        element.transform.width * 0.86 - 26,
        element.transform.height - 42,
      );
    default:
      return false;
  }
}
