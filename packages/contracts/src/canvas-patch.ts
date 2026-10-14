import { z } from 'zod';
import { CanvasDocumentV1Schema, CanvasElementV1Schema, TransformSchema } from './canvas';

const idSchema = z.uuid();

const SetTextOperationSchema = z.object({
  op: z.literal('set_text'),
  element_id: idSchema,
  text: z.string().max(10000),
}).strict();

const SetTransformOperationSchema = z.object({
  op: z.literal('set_transform'),
  element_id: idSchema,
  transform: TransformSchema,
}).strict();

const ReplaceImageAssetOperationSchema = z.object({
  op: z.literal('replace_image_asset'),
  element_id: idSchema,
  asset_version_id: idSchema,
}).strict();

const InsertElementOperationSchema = z.object({
  op: z.literal('insert_element'),
  panel_id: idSchema,
  element: CanvasElementV1Schema,
}).strict();

const RemoveElementOperationSchema = z.object({
  op: z.literal('remove_element'),
  element_id: idSchema,
}).strict();

export const CanvasPatchOperationV1Schema = z.discriminatedUnion('op', [
  SetTextOperationSchema,
  SetTransformOperationSchema,
  ReplaceImageAssetOperationSchema,
  InsertElementOperationSchema,
  RemoveElementOperationSchema,
]);

export const CanvasPatchV1Schema = z.object({
  workspace_id: idSchema,
  ip_id: idSchema,
  episode_id: idSchema,
  document_id: idSchema,
  base_revision: z.number().int().nonnegative(),
  summary: z.string().min(1).max(500),
  operations: z.array(CanvasPatchOperationV1Schema).min(1).max(50),
}).strict();

export const CodexPatchProposalV1Schema = z.object({
  patch_id: idSchema,
  approval_id: idSchema,
  workspace_id: idSchema,
  ip_id: idSchema,
  episode_id: idSchema,
  document_id: idSchema,
  base_revision: z.number().int().nonnegative(),
  patch: CanvasPatchV1Schema,
  preview_document: CanvasDocumentV1Schema,
  status: z.enum(['pending_approval', 'approved', 'rejected']),
  created_by_user_id: idSchema,
  reviewed_by_user_id: idSchema.nullable(),
  reviewed_at: z.string().nullable(),
  review_note: z.string().nullable(),
  applied_revision: z.number().int().positive().nullable(),
  created_at: z.string().min(1),
}).strict();

export type CanvasPatchOperationV1 = z.infer<typeof CanvasPatchOperationV1Schema>;
export type CanvasPatchV1 = z.infer<typeof CanvasPatchV1Schema>;
export type CodexPatchProposalV1 = z.infer<typeof CodexPatchProposalV1Schema>;
