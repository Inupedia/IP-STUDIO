import { z } from 'zod';

const idSchema = z.uuid();

export const TransformSchema = z.object({
  x: z.number().min(-32768).max(32768),
  y: z.number().min(-32768).max(32768),
  width: z.number().positive().max(32768),
  height: z.number().positive().max(32768),
  rotation: z.number().min(-3600).max(3600).default(0),
}).strict();

export const CropSchema = z.object({
  x: z.number().min(0).max(1),
  y: z.number().min(0).max(1),
  width: z.number().positive().max(1),
  height: z.number().positive().max(1),
}).strict().superRefine((crop, context) => {
  if (crop.x + crop.width > 1 || crop.y + crop.height > 1) {
    context.addIssue({ code: 'custom', message: 'Crop rectangle must fit within normalized image bounds' });
  }
});

const ImageElementSchema = z.object({
  id: idSchema,
  type: z.literal('image'),
  asset_version_id: idSchema,
  transform: TransformSchema,
  crop: CropSchema.default({ x: 0, y: 0, width: 1, height: 1 }),
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

const TextPropsSchema = z.object({
  text: z.string().max(10000),
  font_family: z.string().max(120).default('sans-serif'),
  font_size: z.number().positive().max(512).default(32),
  font_weight: z.number().int().min(100).max(900).default(400),
  color: z.string().max(64).default('#242923'),
  align: z.enum(['left', 'center', 'right']).default('left'),
  line_height: z.number().positive().max(10).default(1.3),
  letter_spacing: z.number().min(-20).max(100).default(0),
}).strict();

const TextElementSchema = z.object({
  id: idSchema,
  type: z.literal('text'),
  props: TextPropsSchema,
  transform: TransformSchema,
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

const BubblePropsSchema = z.object({
  text: z.string().max(10000),
  shape: z.enum(['rounded_rectangle', 'ellipse', 'cloud']).default('rounded_rectangle'),
  fill: z.string().max(64).default('#ffffff'),
  stroke: z.string().max(64).default('#242923'),
  stroke_width: z.number().min(0).max(64).default(2),
  tail_position: z.enum(['left', 'right', 'top', 'bottom', 'none']).default('bottom'),
  font_family: z.string().max(120).default('sans-serif'),
  font_size: z.number().positive().max(512).default(28),
}).strict();

const SpeechBubbleSchema = z.object({
  id: idSchema,
  type: z.literal('speech_bubble'),
  props: BubblePropsSchema,
  transform: TransformSchema,
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

const ThoughtBubbleSchema = z.object({
  id: idSchema,
  type: z.literal('thought_bubble'),
  props: BubblePropsSchema,
  transform: TransformSchema,
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

const ChatMessagePropsSchema = z.object({
  self_participant_id: idSchema,
  sender_id: idSchema,
  text: z.string().max(10000),
  sent_at: z.string().max(40),
  theme: z.enum(['light', 'dark']).default('light'),
  direction_override: z.enum(['left', 'right']).nullable().optional(),
}).strict();

const ChatMessageSchema = z.object({
  id: idSchema,
  type: z.literal('chat_message'),
  props: ChatMessagePropsSchema,
  transform: TransformSchema,
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

const ShapePropsSchema = z.object({
  shape: z.enum(['rectangle', 'rounded_rectangle', 'ellipse', 'line', 'arrow']),
  fill: z.string().max(64).nullable().default(null),
  stroke: z.string().max(64).default('#242923'),
  stroke_width: z.number().min(0).max(64).default(2),
}).strict();

const ShapeSchema = z.object({
  id: idSchema,
  type: z.literal('shape'),
  props: ShapePropsSchema,
  transform: TransformSchema,
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

const StickerSchema = z.object({
  id: idSchema,
  type: z.literal('sticker'),
  asset_version_id: idSchema,
  transform: TransformSchema,
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

const PanelFrameSchema = z.object({
  id: idSchema,
  type: z.literal('panel_frame'),
  props: z.object({
    stroke: z.string().max(64).default('#242923'),
    stroke_width: z.number().min(0).max(64).default(2),
    fill: z.string().max(64).nullable().default(null),
  }).strict(),
  transform: TransformSchema,
  opacity: z.number().min(0).max(1).default(1),
  z_index: z.number().int().min(0),
  locked: z.boolean().default(false),
}).strict();

export const CanvasElementV1Schema = z.discriminatedUnion('type', [
  ImageElementSchema,
  TextElementSchema,
  SpeechBubbleSchema,
  ThoughtBubbleSchema,
  ChatMessageSchema,
  ShapeSchema,
  StickerSchema,
  PanelFrameSchema,
]);

export const RectSchema = z.object({
  x: z.number().min(0),
  y: z.number().min(0),
  width: z.number().positive(),
  height: z.number().positive(),
}).strict();

const PanelSchema = z.object({
  id: idSchema,
  rect: RectSchema,
  elements: z.array(CanvasElementV1Schema),
}).strict();

const PageSchema = z.object({
  id: idSchema,
  width: z.number().int().positive().max(8192),
  height: z.number().int().positive().max(8192),
  order: z.number().int().positive(),
  layout_code: z.enum(['four', 'six', 'eight', 'custom']),
  brand_template_version_id: idSchema,
  panels: z.array(PanelSchema).min(1),
}).strict().superRefine((page, context) => {
  page.panels.forEach((panel, index) => {
    if (panel.rect.x + panel.rect.width > page.width || panel.rect.y + panel.rect.height > page.height) {
      context.addIssue({ code: 'custom', message: `Panel ${panel.id} falls outside the page`, path: ['panels', index, 'rect'] });
    }
  });
});

export const CanvasDocumentV1Schema = z.object({
  schema_version: z.literal('1.0'),
  episode_id: idSchema,
  revision: z.number().int().min(0),
  style_version_id: idSchema.nullable(),
  brand_template_version_id: idSchema,
  dynamic_fields: z.object({
    title: z.string().max(1000),
    episode_number: z.string().max(32),
  }).strict(),
  pages: z.array(PageSchema).min(1),
}).strict().superRefine((document, context) => {
  const pageOrders = document.pages.map((page) => page.order);
  if (new Set(pageOrders).size !== pageOrders.length) {
    context.addIssue({ code: 'custom', message: 'Page order values must be unique', path: ['pages'] });
  }
  document.pages.forEach((page, index) => {
    if (page.brand_template_version_id !== document.brand_template_version_id) {
      context.addIssue({ code: 'custom', message: 'Every page must use the document brand template version', path: ['pages', index, 'brand_template_version_id'] });
    }
  });
});

export type CanvasDocumentV1 = z.infer<typeof CanvasDocumentV1Schema>;
export type CanvasElementV1 = z.infer<typeof CanvasElementV1Schema>;
export type ChatMessagePropsV1 = z.infer<typeof ChatMessagePropsSchema>;

export function parseCanvasDocument(input: unknown): CanvasDocumentV1 {
  return CanvasDocumentV1Schema.parse(input);
}

export function resolveMessageSide(senderId: string, selfId: string): 'left' | 'right' {
  return senderId === selfId ? 'right' : 'left';
}
