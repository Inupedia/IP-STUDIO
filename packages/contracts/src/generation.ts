import { z } from 'zod';

const idSchema = z.uuid();

const CharacterReferenceV1Schema = z.object({
  kind: z.literal('character_version'),
  version_id: idSchema,
  entity_id: idSchema,
  version_no: z.number().int().positive(),
  name: z.string(),
  bible: z.record(z.string(), z.unknown()),
  bible_summary: z.string(),
}).passthrough();

const StyleReferenceV1Schema = z.object({
  kind: z.literal('style_version'),
  version_id: idSchema,
  entity_id: idSchema,
  version_no: z.number().int().positive(),
  name: z.string(),
  bible: z.record(z.string(), z.unknown()),
  bible_summary: z.string(),
}).passthrough();

const AssetReferenceV1Schema = z.object({
  kind: z.literal('asset_version'),
  version_id: idSchema,
  asset_id: idSchema,
  version_no: z.number().int().positive(),
  name: z.string(),
  asset_type: z.string(),
  mime: z.enum(['image/png', 'image/jpeg', 'image/webp']),
  sha256: z.string().regex(/^[0-9a-f]{64}$/),
  byte_size: z.number().int().positive(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
}).passthrough();

export const GenerationReferenceV1Schema = z.discriminatedUnion('kind', [
  CharacterReferenceV1Schema,
  StyleReferenceV1Schema,
  AssetReferenceV1Schema,
]);

export const PromptSnapshotV1Schema = z.object({
  schema_version: z.literal('1.0'),
  text: z.string(),
  panel: z.record(z.string(), z.unknown()),
  locked_version_ids: z.array(idSchema),
}).passthrough();

export const GenerationTaskV1Schema = z.object({
  task_id: idSchema,
  episode_id: idSchema,
  script_revision_id: idSchema,
  script_revision_no: z.number().int().positive(),
  panel_id: idSchema,
  mode: z.literal('chatgpt_web'),
  status: z.enum(['prepared', 'waiting_manual_generation', 'asset_imported']),
  prompt_snapshot: PromptSnapshotV1Schema,
  reference_snapshot: z.array(GenerationReferenceV1Schema),
  reference_bundle_url: z.string().min(1),
  // SQLite emits local timestamps in API tests while PostgreSQL uses UTC offsets.
  created_at: z.string().min(1),
}).strict();

export const GenerationCandidateV1Schema = z.object({
  candidate_id: idSchema,
  task_id: idSchema,
  panel_id: idSchema,
  asset_version_id: idSchema,
  status: z.enum(['pending_review', 'approved', 'rejected']),
  created_at: z.string().min(1),
}).strict();

export type GenerationReferenceV1 = z.infer<typeof GenerationReferenceV1Schema>;
export type GenerationTaskV1 = z.infer<typeof GenerationTaskV1Schema>;
export type GenerationCandidateV1 = z.infer<typeof GenerationCandidateV1Schema>;

export interface GenerationTaskCreateV1 {
  script_revision_no: number;
  panel_id: string;
  reference_version_ids?: string[];
  mode?: 'chatgpt_web';
}
