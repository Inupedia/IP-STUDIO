import { describe, expect, it } from 'vitest';
import { applyLayout, getLayout, LayoutTemplateSchema } from './layout';

function overlaps(a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) {
  return !(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y);
}

describe('panel layouts', () => {
  it.each([
    ['four', 4],
    ['six', 6],
    ['eight', 8],
  ] as const)('creates %s with %s non-overlapping panels', (code, count) => {
    const layout = getLayout(code);
    expect(layout.panels).toHaveLength(count);
    layout.panels.forEach((panel, index) => {
      layout.panels.slice(index + 1).forEach((other) => expect(overlaps(panel, other)).toBe(false));
    });
  });

  it('keeps the page brand version when changing panel layout', () => {
    const page = {
      brand_template_version_id: 'brand-v1',
      panels: [{ panel_id: 'stable-panel-id', elements: [{ id: 'text-1' }] }],
    };
    const updated = applyLayout(page, getLayout('six'));
    expect(updated.brand_template_version_id).toBe('brand-v1');
    expect(updated.panels[0].panel_id).toBe('stable-panel-id');
    expect(updated.panels[0].elements).toEqual([{ id: 'text-1' }]);
    expect(updated.panels).toHaveLength(6);
  });

  it('rejects overlapping custom panel geometry', () => {
    const result = LayoutTemplateSchema.safeParse({
      code: 'custom',
      width: 500,
      height: 500,
      margin: 0,
      gap: 0,
      panels: [
        { panel_id: 'one', x: 0, y: 0, width: 250, height: 250 },
        { panel_id: 'two', x: 100, y: 100, width: 250, height: 250 },
      ],
    });
    expect(result.success).toBe(false);
  });
});
