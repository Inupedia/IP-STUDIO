import { z } from 'zod';

export const PanelGeometrySchema = z.object({
  panel_id: z.string().min(1).max(80),
  x: z.number().min(0),
  y: z.number().min(0),
  width: z.number().positive(),
  height: z.number().positive(),
}).strict();

export const LayoutTemplateSchema = z.object({
  code: z.enum(['four', 'six', 'eight', 'custom']),
  width: z.number().positive(),
  height: z.number().positive(),
  margin: z.number().min(0),
  gap: z.number().min(0),
  panels: z.array(PanelGeometrySchema).min(1),
}).strict().superRefine((layout, context) => {
  const ids = layout.panels.map((panel) => panel.panel_id);
  if (new Set(ids).size !== ids.length) {
    context.addIssue({ code: 'custom', message: 'Panel ids must be unique', path: ['panels'] });
  }
  layout.panels.forEach((panel, index) => {
    if (panel.x + panel.width > layout.width || panel.y + panel.height > layout.height) {
      context.addIssue({ code: 'custom', message: `Panel ${panel.panel_id} falls outside the page`, path: ['panels', index] });
    }
    layout.panels.slice(index + 1).forEach((other, offset) => {
      const separated = panel.x + panel.width <= other.x
        || other.x + other.width <= panel.x
        || panel.y + panel.height <= other.y
        || other.y + other.height <= panel.y;
      if (!separated) {
        context.addIssue({ code: 'custom', message: `Panels ${panel.panel_id} and ${other.panel_id} overlap`, path: ['panels', index + offset + 1] });
      }
    });
  });
});

export type LayoutCode = 'four' | 'six' | 'eight' | 'custom';
export type PanelGeometry = z.infer<typeof PanelGeometrySchema>;
export type LayoutTemplate = z.infer<typeof LayoutTemplateSchema>;

const rowCounts = { four: 2, six: 3, eight: 4 } as const;

export function getLayout(code: Exclude<LayoutCode, 'custom'>, width = 1080, height = 1440, margin = 48, gap = 24): LayoutTemplate {
  const rows = rowCounts[code];
  const columns = 2;
  if (width <= margin * 2 || height <= margin * 2 || gap < 0) {
    throw new Error('Page size must leave room for layout margins');
  }
  const panelWidth = (width - margin * 2 - gap * (columns - 1)) / columns;
  const panelHeight = (height - margin * 2 - gap * (rows - 1)) / rows;
  if (panelWidth <= 0 || panelHeight <= 0) throw new Error('Page size is too small for the requested layout');
  return LayoutTemplateSchema.parse({
    code,
    width,
    height,
    margin,
    gap,
    panels: Array.from({ length: rows * columns }, (_, index) => {
      const row = Math.floor(index / columns);
      const column = index % columns;
      return {
        panel_id: `panel-${String(index + 1).padStart(2, '0')}`,
        x: margin + column * (panelWidth + gap),
        y: margin + row * (panelHeight + gap),
        width: panelWidth,
        height: panelHeight,
      };
    }),
  });
}

export function applyLayout<TPage extends { brand_template_version_id: string; panels?: Array<{ elements?: unknown[]; [key: string]: unknown }> }>(page: TPage, layout: LayoutTemplate): TPage & { layout_code: LayoutCode; width: number; height: number; panels: Array<PanelGeometry & { elements: unknown[] }> } {
  const validatedLayout = LayoutTemplateSchema.parse(layout);
  const previousPanels = page.panels ?? [];
  if (previousPanels.length > validatedLayout.panels.length
    && previousPanels.slice(validatedLayout.panels.length).some((panel) => panel.elements?.length)) {
    throw new Error('Changing this layout would discard panel elements');
  }
  return {
    ...page,
    layout_code: validatedLayout.code,
    width: validatedLayout.width,
    height: validatedLayout.height,
    panels: validatedLayout.panels.map((geometry, index) => ({
      ...previousPanels[index],
      ...geometry,
      elements: previousPanels[index]?.elements ?? [],
    })),
  };
}
