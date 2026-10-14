import { describe, expect, it } from 'vitest';
import { ProjectManifestV1Schema } from './project-manifest';

const manifest = {
  schema_version: '1.0',
  exported_at: '2026-10-14T00:00:00Z',
  source: {
    workspace_id: '10000000-0000-4000-8000-000000000001',
    ip_id: '10000000-0000-4000-8000-000000000002',
    ip_code: 'LAG',
    ip_name: '卡仔',
    series_id: '10000000-0000-4000-8000-000000000003',
    series_name: '人间卡顿局',
    series_summary: null,
    episode_id: '10000000-0000-4000-8000-000000000004',
    episode_number: 1,
    episode_title: '在吗？',
    episode_status: 'draft',
    episode_default_style_version_id: null,
    revision_no: 3,
  },
  brand: {
    template_id: '10000000-0000-4000-8000-000000000005',
    template_name: '固定外壳',
    version_id: '10000000-0000-4000-8000-000000000006',
    version_no: 1,
    approved_at: '2026-10-14T00:00:00Z',
    template_json: {
      schema_version: '1.0',
      width: 1080,
      height: 1440,
      locked_elements: [
        { id: 'logo', kind: 'logo', locked: true, x: 20, y: 20, width: 100, height: 50, fill: '#123456' },
      ],
      dynamic_slots: {
        title: { x: 100, y: 30, width: 800, height: 80 },
        episode_number: { x: 900, y: 30, width: 100, height: 50 },
      },
    },
  },
  styles: [],
  assets: [{
    asset_id: '10000000-0000-4000-8000-000000000007',
    asset_version_id: '10000000-0000-4000-8000-000000000008',
    version_no: 2,
    name: '角色图',
    type: 'character_reference',
    source_type: 'uploaded',
    rights_note: null,
    status: 'approved',
    width: 10,
    height: 20,
    alpha: true,
    metadata_json: {},
    sha256: '0'.repeat(64),
    mime: 'image/png',
    byte_size: 100,
    blob_path: `blobs/${'0'.repeat(64)}.png`,
    approved_at: '2026-10-14T00:00:00Z',
  }],
};

describe('ProjectManifestV1Schema', () => {
  it('accepts a portable manifest with hashed relative blob paths', () => {
    expect(ProjectManifestV1Schema.parse(manifest).assets).toHaveLength(1);
  });

  it('rejects mismatched blob paths and invalid hashes', () => {
    const invalid = structuredClone(manifest);
    invalid.assets[0].blob_path = '../outside.png';
    invalid.assets[0].sha256 = 'not-a-hash';
    expect(ProjectManifestV1Schema.safeParse(invalid).success).toBe(false);
  });

  it('rejects duplicate version numbers for one asset', () => {
    const invalid = structuredClone(manifest);
    invalid.assets.push({
      ...invalid.assets[0],
      asset_version_id: '10000000-0000-4000-8000-000000000009',
    });
    expect(ProjectManifestV1Schema.safeParse(invalid).success).toBe(false);
  });
});
