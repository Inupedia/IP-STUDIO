import { describe, expect, it } from 'vitest';
import { BrandTemplateV1Schema } from './brand';

const template = {
  schema_version: '1.0',
  width: 1080,
  height: 1440,
  locked_elements: [{
    id: 'logo',
    kind: 'logo',
    locked: true,
    x: 20,
    y: 20,
    width: 120,
    height: 40,
  }],
  dynamic_slots: {
    title: { x: 100, y: 40, width: 800, height: 100 },
    episode_number: { x: 900, y: 30, width: 120, height: 60 },
  },
};

describe('BrandTemplateV1', () => {
  it('accepts a locked shell and the two dynamic content slots', () => {
    expect(BrandTemplateV1Schema.safeParse(template).success).toBe(true);
  });

  it('rejects unlocked elements and geometry outside the page', () => {
    expect(BrandTemplateV1Schema.safeParse({
      ...template,
      locked_elements: [{ ...template.locked_elements[0], locked: false }],
    }).success).toBe(false);
    expect(BrandTemplateV1Schema.safeParse({
      ...template,
      dynamic_slots: { ...template.dynamic_slots, title: { x: 1000, y: 40, width: 800, height: 100 } },
    }).success).toBe(false);
  });
});
