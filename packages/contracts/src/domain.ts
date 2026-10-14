export type AssetType =
  | 'character_reference'
  | 'character_pose'
  | 'expression'
  | 'scene'
  | 'background'
  | 'prop'
  | 'composite_panel'
  | 'texture'
  | 'other';

export type VersionStatus = 'candidate' | 'approved' | 'archived';

export interface IP {
  id: string;
  code: string;
  name: string;
  summary: string | null;
  status: string;
  default_style_version_id: string | null;
  created_at: string;
}

export interface IPCreate {
  code: string;
  name: string;
  summary?: string | null;
}

export interface DefaultStyleSelection {
  ip_id: string;
  default_style_version_id: string;
}

export interface AssetVersion {
  asset_id: string;
  asset_version_id: string;
  workspace_id: string;
  owner_ip_id: string;
  type: AssetType;
  name: string;
  status: VersionStatus;
  version_no: number;
  sha256: string;
  mime: 'image/png' | 'image/jpeg' | 'image/webp';
  byte_size: number;
  width: number;
  height: number;
  alpha: boolean;
  created_at: string;
}

export interface CharacterBible {
  personality?: string;
  language_style?: string;
  fixed_appearance?: string;
  invariants?: string[];
  palette?: Record<string, string>;
  prohibited_features?: string[];
  standard_reference_asset_version_ids?: string[];
  expression_asset_version_ids?: string[];
  pose_asset_version_ids?: string[];
  costume_asset_version_ids?: string[];
  tags?: string[];
}

export interface StyleBible {
  linework_rules?: string[];
  palette?: Record<string, string>;
  lighting?: string;
  materials?: string[];
  aspect_ratios?: string[];
  positive_rules?: string[];
  negative_rules?: string[];
  example_asset_version_ids?: string[];
  font_rules?: string;
  speech_bubble_rules?: string;
  tags?: string[];
}

export interface CharacterVersion {
  character_version_id: string;
  character_id: string;
  version_no: number;
  status: VersionStatus;
  bible: CharacterBible;
  derived_from_version_id: string | null;
  approved_at: string | null;
}

export interface StyleVersion {
  style_version_id: string;
  style_id: string;
  version_no: number;
  status: VersionStatus;
  bible: StyleBible;
  derived_from_version_id: string | null;
  approved_at: string | null;
}

export interface Character {
  character_id: string;
  ip_id: string;
  code: string;
  name: string;
  versions: CharacterVersion[];
}

export interface Style {
  style_id: string;
  ip_id: string;
  name: string;
  versions: StyleVersion[];
}

export interface AdminProfile {
  id: string;
  workspace_id: string;
  email: string;
  is_admin: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
}
