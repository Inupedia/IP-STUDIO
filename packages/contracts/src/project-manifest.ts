import { z } from 'zod';
import { BrandTemplateV1Schema } from './brand';

const idSchema = z.uuid();
const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);

const assetTypeSchema = z.enum([
  'character_reference', 'character_pose', 'expression', 'scene', 'background',
  'prop', 'composite_panel', 'texture', 'other',
]);
const assetSourceSchema = z.enum(['chatgpt_web', 'codex_native', 'uploaded', 'edited_locally', 'other']);
const mimeSchema = z.enum(['image/png', 'image/jpeg', 'image/webp']);

export const ProjectAssetSnapshotV1Schema = z.object({
  asset_id: idSchema,
  asset_version_id: idSchema,
  version_no: z.number().int().positive(),
  name: z.string().min(1).max(200),
  type: assetTypeSchema,
  source_type: assetSourceSchema,
  rights_note: z.string().nullable(),
  status: z.literal('approved'),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  alpha: z.boolean(),
  metadata_json: z.record(z.string(), z.unknown()),
  approved_at: z.iso.datetime(),
  sha256: sha256Schema,
  mime: mimeSchema,
  byte_size: z.number().int().positive(),
  blob_path: z.string().min(1),
}).strict().superRefine((asset, context) => {
  const extension = asset.mime === 'image/png' ? 'png' : asset.mime === 'image/jpeg' ? 'jpg' : 'webp';
  if (asset.blob_path !== `blobs/${asset.sha256}.${extension}`) {
    context.addIssue({ code: 'custom', message: 'Blob path must match the content hash and MIME type', path: ['blob_path'] });
  }
});

export const ProjectStyleSnapshotV1Schema = z.object({
  style_id: idSchema,
  style_name: z.string().min(1).max(120),
  version_id: idSchema,
  version_no: z.number().int().positive(),
  approved_at: z.iso.datetime(),
  bible_json: z.record(z.string(), z.unknown()),
}).strict();

export const ProjectManifestV1Schema = z.object({
  schema_version: z.literal('1.0'),
  exported_at: z.iso.datetime(),
  source: z.object({
    workspace_id: idSchema,
    ip_id: idSchema,
    ip_code: z.string().min(1).max(32),
    ip_name: z.string().min(1).max(120),
    series_id: idSchema,
    series_name: z.string().min(1).max(120),
    series_summary: z.string().nullable(),
    episode_id: idSchema,
    episode_number: z.number().int().positive(),
    episode_title: z.string().min(1).max(200),
    episode_status: z.string().min(1).max(24),
    episode_default_style_version_id: idSchema.nullable(),
    revision_no: z.number().int().positive(),
  }).strict(),
  brand: z.object({
    template_id: idSchema,
    template_name: z.string().min(1).max(120),
    version_id: idSchema,
    version_no: z.number().int().positive(),
    approved_at: z.iso.datetime(),
    template_json: BrandTemplateV1Schema,
  }).strict(),
  styles: z.array(ProjectStyleSnapshotV1Schema),
  assets: z.array(ProjectAssetSnapshotV1Schema),
}).strict().superRefine((manifest, context) => {
  const versionIds = manifest.assets.map((asset) => asset.asset_version_id);
  if (new Set(versionIds).size !== versionIds.length) {
    context.addIssue({ code: 'custom', message: 'Asset version IDs must be unique', path: ['assets'] });
  }
  const styleIds = manifest.styles.map((style) => style.version_id);
  if (new Set(styleIds).size !== styleIds.length) {
    context.addIssue({ code: 'custom', message: 'Style version IDs must be unique', path: ['styles'] });
  }
  const assetsById = new Map<string, z.infer<typeof ProjectAssetSnapshotV1Schema>[]>();
  for (const asset of manifest.assets) {
    const versions = assetsById.get(asset.asset_id) ?? [];
    versions.push(asset);
    assetsById.set(asset.asset_id, versions);
  }
  for (const [assetId, versions] of assetsById) {
    const metadata = new Set(versions.map((asset) => JSON.stringify([
      asset.name, asset.type, asset.source_type, asset.rights_note,
    ])));
    const versionNumbers = versions.map((asset) => asset.version_no);
    if (metadata.size !== 1 || new Set(versionNumbers).size !== versionNumbers.length) {
      context.addIssue({
        code: 'custom',
        message: 'Asset versions must share metadata and use unique version numbers',
        path: ['assets', assetId],
      });
    }
  }
  const stylesById = new Map<string, z.infer<typeof ProjectStyleSnapshotV1Schema>[]>();
  for (const style of manifest.styles) {
    const versions = stylesById.get(style.style_id) ?? [];
    versions.push(style);
    stylesById.set(style.style_id, versions);
  }
  for (const [styleId, versions] of stylesById) {
    const versionNumbers = versions.map((style) => style.version_no);
    if (
      new Set(versions.map((style) => style.style_name)).size !== 1
      || new Set(versionNumbers).size !== versionNumbers.length
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Style versions must share a name and use unique version numbers',
        path: ['styles', styleId],
      });
    }
  }
});

export type ProjectManifestV1 = z.infer<typeof ProjectManifestV1Schema>;
export type ProjectAssetSnapshotV1 = z.infer<typeof ProjectAssetSnapshotV1Schema>;
