import { describe, expect, it } from 'vitest';
import { mayOverflowTextBox } from './textOverflow';

describe('mayOverflowTextBox', () => {
  it('estimates Chinese wrapping and reports text that cannot fit the box', () => {
    expect(mayOverflowTextBox('加班'.repeat(40), 36, 1.3, 500, 100)).toBe(true);
    expect(mayOverflowTextBox('今天又加班', 28, 1.2, 500, 100)).toBe(false);
  });
});
