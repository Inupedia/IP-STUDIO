import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LayoutPicker } from './LayoutPicker';

describe('LayoutPicker', () => {
  it('offers the four, six, and eight panel layouts without changing the brand version', () => {
    const onSelect = vi.fn();
    render(<LayoutPicker value="four" onChange={onSelect} brandVersionLabel="品牌 v1" />);

    fireEvent.click(screen.getByRole('button', { name: /六格/ }));

    expect(onSelect).toHaveBeenCalledWith('six');
    expect(screen.getByText('品牌 v1')).toBeTruthy();
    expect(screen.getByRole('button', { name: /四格/ }).getAttribute('aria-pressed')).toBe('true');
  });
});
