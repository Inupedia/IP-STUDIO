import { z } from 'zod';

export const LockedBrandElementSchema = z.object({
  id: z.string().min(1).max(80),
  kind: z.enum(['background', 'logo', 'decoration', 'title_bar', 'footer']),
  locked: z.literal(true),
  x: z.number().min(0),
  y: z.number().min(0),
  width: z.number().positive(),
  height: z.number().positive(),
  asset_version_id: z.uuid().nullable().optional(),
  fill: z.string().max(64).nullable().optional(),
  opacity: z.number().min(0).max(1).default(1),
}).strict();

export const DynamicSlotSchema = z.object({
  x: z.number().min(0),
  y: z.number().min(0),
  width: z.number().positive(),
  height: z.number().positive(),
  font_family: z.string().max(120).default('sans-serif'),
  font_size: z.number().positive().max(512).default(48),
  color: z.string().max(64).default('#242923'),
  align: z.enum(['left', 'center', 'right']).default('left'),
}).strict();

export const BrandTemplateV1Schema = z.object({
  schema_version: z.literal('1.0').default('1.0'),
  width: z.number().int().positive().max(8192),
  height: z.number().int().positive().max(8192),
  locked_elements: z.array(LockedBrandElementSchema).min(1).max(100)
    .refine((elements) => new Set(elements.map((element) => element.id)).size === elements.length,
      'Brand element ids must be unique'),
  dynamic_slots: z.object({
    title: DynamicSlotSchema,
    episode_number: DynamicSlotSchema,
  }).strict(),
}).strict().superRefine((template, context) => {
  for (const element of template.locked_elements) {
    if (element.x + element.width > template.width || element.y + element.height > template.height) {
      context.addIssue({ code: 'custom', message: `Brand element ${element.id} falls outside the page`, path: ['locked_elements'] });
    }
  }
  for (const [slotName, slot] of Object.entries(template.dynamic_slots)) {
    if (slot.x + slot.width > template.width || slot.y + slot.height > template.height) {
      context.addIssue({ code: 'custom', message: `Dynamic slot ${slotName} falls outside the page`, path: ['dynamic_slots', slotName] });
    }
  }
});

export type LockedBrandElement = z.infer<typeof LockedBrandElementSchema>;
export type DynamicSlot = z.infer<typeof DynamicSlotSchema>;
export type BrandTemplateV1 = z.infer<typeof BrandTemplateV1Schema>;
