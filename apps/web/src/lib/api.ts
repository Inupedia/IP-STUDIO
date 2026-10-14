import type {
  AdminProfile,
  AssetType,
  AssetVersion,
  Character,
  CharacterBible,
  CharacterVersion,
  DefaultStyleSelection,
  IP,
  IPCreate,
  Style,
  StyleBible,
  StyleVersion,
  TokenResponse,
} from '@ip-studio/contracts/domain';
import type { CanvasDocumentV1, DocumentReadV1, DocumentRevisionReadV1 } from '@ip-studio/contracts/canvas';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { ScriptMaterializationResultV1, ScriptRevisionReadV1, ScriptV1 } from '@ip-studio/contracts/script';
import type {
  GenerationCandidateV1,
  GenerationTaskCreateV1,
  GenerationTaskV1,
} from '@ip-studio/contracts/generation';
import type { CodexCapabilityV1, CodexRunV1 } from '@ip-studio/contracts/codex';
import type { CodexPatchProposalV1 } from '@ip-studio/contracts/canvas-patch';

export interface ExportJobReadV1 {
  id: string;
  episode_id: string;
  revision_no: number;
  format: 'png_zip' | 'project_zip' | 'pptx';
  status: 'complete' | 'failed';
  page_count: number;
  warnings: string[];
  download_url: string | null;
  created_at: string;
}

export interface SeriesReadV1 {
  id: string;
  ip_id: string;
  name: string;
  summary: string | null;
  created_at: string;
}

export interface EpisodeReadV1 {
  id: string;
  series_id: string;
  number: number;
  title: string;
  status: string;
  created_at: string;
}

export interface BrandTemplateVersionReadV1 {
  brand_template_version_id: string;
  brand_template_id: string;
  version_no: number;
  status: 'candidate' | 'approved' | 'archived';
  template: BrandTemplateV1;
  derived_from_version_id: string | null;
  approved_at: string | null;
}

export interface BrandTemplateReadV1 {
  brand_template_id: string;
  ip_id: string;
  name: string;
  versions: BrandTemplateVersionReadV1[];
}

const TOKEN_KEY = 'ip-studio-access-token';
const AUTH_EXPIRED_EVENT = 'ip-studio:auth-expired';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

let accessToken: string | null =
  typeof window === 'undefined' ? null : window.sessionStorage.getItem(TOKEN_KEY);

export function setAccessToken(token: string | null): void {
  accessToken = token;
  if (typeof window === 'undefined') return;
  if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
  else window.sessionStorage.removeItem(TOKEN_KEY);
}

export function getAccessToken(): string | null {
  return accessToken;
}

function expireAccessToken(): void {
  setAccessToken(null);
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}

export const authExpiredEvent = AUTH_EXPIRED_EVENT;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (authenticated && accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    let detail: unknown;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = body.detail;
      if (typeof body.detail === 'string') message = body.detail;
      else if (typeof body.detail === 'object' && body.detail !== null && 'message' in body.detail
        && typeof body.detail.message === 'string') message = body.detail.message;
    } catch {
      // Keep the status-based message when the server does not return JSON.
    }
    if (response.status === 401) expireAccessToken();
    throw new ApiError(message, response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

export const api = {
  async login(email: string, password: string): Promise<TokenResponse> {
    const body = new URLSearchParams({ username: email, password });
    const result = await request<TokenResponse>(
      '/api/v1/auth/token',
      { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
      false,
    );
    setAccessToken(result.access_token);
    return result;
  },

  getCurrentAdmin(): Promise<AdminProfile> {
    return request('/api/v1/auth/me');
  },

  getIps(): Promise<IP[]> {
    return request('/api/v1/ips');
  },

  getSeries(ipId: string): Promise<SeriesReadV1[]> {
    return request(`/api/v1/series?ip_id=${encodeURIComponent(ipId)}`);
  },

  createSeries(ipId: string, name: string, summary?: string): Promise<SeriesReadV1> {
    return request('/api/v1/series', {
      method: 'POST',
      body: jsonBody({ ip_id: ipId, name, summary: summary || null }),
    });
  },

  getEpisodes(seriesId: string): Promise<EpisodeReadV1[]> {
    return request(`/api/v1/series/${seriesId}/episodes`);
  },

  createEpisode(seriesId: string, number: number, title: string): Promise<EpisodeReadV1> {
    return request(`/api/v1/series/${seriesId}/episodes`, {
      method: 'POST',
      body: jsonBody({ number, title }),
    });
  },

  getBrandTemplates(ipId: string): Promise<BrandTemplateReadV1[]> {
    return request(`/api/v1/ips/${ipId}/brand-templates`);
  },

  createBrandTemplate(
    ipId: string,
    name: string,
    template: BrandTemplateV1,
  ): Promise<BrandTemplateVersionReadV1> {
    return request(`/api/v1/ips/${ipId}/brand-templates`, {
      method: 'POST',
      body: jsonBody({ name, template }),
    });
  },

  getBrandTemplateVersion(versionId: string): Promise<BrandTemplateVersionReadV1> {
    return request(`/api/v1/brand-template-versions/${versionId}`);
  },

  approveBrandTemplateVersion(versionId: string): Promise<BrandTemplateVersionReadV1> {
    return request(`/api/v1/brand-template-versions/${versionId}/approve`, { method: 'POST' });
  },

  createIp(payload: IPCreate): Promise<IP> {
    return request('/api/v1/ips', { method: 'POST', body: jsonBody(payload) });
  },

  getAssets(ipId: string): Promise<AssetVersion[]> {
    return request(`/api/v1/assets?ip_id=${encodeURIComponent(ipId)}`);
  },

  uploadAsset(
    file: File,
    ipId: string,
    name: string,
    type: AssetType,
    rightsNote?: string,
  ): Promise<AssetVersion> {
    const body = new FormData();
    body.set('ip_id', ipId);
    body.set('name', name);
    body.set('type', type);
    if (rightsNote) body.set('rights_note', rightsNote);
    body.set('file', file);
    return request('/api/v1/assets/upload', { method: 'POST', body });
  },

  approveAssetVersion(ipId: string, assetId: string, versionId: string): Promise<AssetVersion> {
    const query = new URLSearchParams({ ip_id: ipId });
    return request(`/api/v1/assets/${assetId}/versions/${versionId}/approve?${query}`, {
      method: 'POST',
    });
  },

  async getAssetPreview(ipId: string, assetId: string, versionId: string): Promise<string> {
    const query = new URLSearchParams({ ip_id: ipId, version_id: versionId });
    const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined;
    const response = await fetch(
      `${API_BASE_URL}/api/v1/assets/${assetId}/content?${query}`,
      { headers },
    );
    if (!response.ok) {
      if (response.status === 401) expireAccessToken();
      throw new ApiError('无法加载素材预览', response.status);
    }
    return URL.createObjectURL(await response.blob());
  },

  getCharacters(ipId: string): Promise<Character[]> {
    return request(`/api/v1/ips/${ipId}/characters`);
  },

  createCharacter(
    ipId: string,
    payload: { code: string; name: string; bible: CharacterBible },
  ): Promise<CharacterVersion> {
    return request(`/api/v1/ips/${ipId}/characters`, {
      method: 'POST',
      body: jsonBody(payload),
    });
  },

  createCharacterVersion(
    characterId: string,
    payload: { base_version_id?: string; bible: CharacterBible },
  ): Promise<CharacterVersion> {
    return request(`/api/v1/characters/${characterId}/versions`, {
      method: 'POST',
      body: jsonBody(payload),
    });
  },

  approveCharacterVersion(versionId: string): Promise<CharacterVersion> {
    return request(`/api/v1/character-versions/${versionId}/approve`, { method: 'POST' });
  },

  getStyles(ipId: string): Promise<Style[]> {
    return request(`/api/v1/ips/${ipId}/styles`);
  },

  createStyle(ipId: string, payload: { name: string; bible: StyleBible }): Promise<StyleVersion> {
    return request(`/api/v1/ips/${ipId}/styles`, { method: 'POST', body: jsonBody(payload) });
  },

  createStyleVersion(
    styleId: string,
    payload: { base_version_id?: string; bible: StyleBible },
  ): Promise<StyleVersion> {
    return request(`/api/v1/styles/${styleId}/versions`, {
      method: 'POST',
      body: jsonBody(payload),
    });
  },

  approveStyleVersion(versionId: string): Promise<StyleVersion> {
    return request(`/api/v1/style-versions/${versionId}/approve`, { method: 'POST' });
  },

  setDefaultStyle(ipId: string, styleVersionId: string): Promise<DefaultStyleSelection> {
    return request(`/api/v1/ips/${ipId}/default-style`, {
      method: 'PUT',
      body: jsonBody({ style_version_id: styleVersionId }),
    });
  },

  getEpisodeDocument(episodeId: string): Promise<DocumentReadV1> {
    return request(`/api/v1/episodes/${episodeId}/document`);
  },

  saveEpisodeDocument(
    episodeId: string,
    baseRevision: number,
    document: CanvasDocumentV1,
    note?: string,
  ): Promise<DocumentReadV1> {
    return request(`/api/v1/episodes/${episodeId}/document`, {
      method: 'PUT',
      body: jsonBody({ base_revision: baseRevision, document, note }),
    });
  },

  getDocumentRevisions(episodeId: string): Promise<DocumentRevisionReadV1[]> {
    return request(`/api/v1/episodes/${episodeId}/revisions`);
  },

  restoreDocumentRevision(
    episodeId: string,
    revisionNo: number,
    baseRevision: number,
  ): Promise<DocumentReadV1> {
    return request(`/api/v1/episodes/${episodeId}/restore/${revisionNo}`, {
      method: 'POST',
      body: jsonBody({ base_revision: baseRevision }),
    });
  },

  getEpisodeScripts(episodeId: string): Promise<ScriptRevisionReadV1[]> {
    return request(`/api/v1/episodes/${episodeId}/scripts`);
  },

  getEpisodeScript(episodeId: string, revisionNo: number): Promise<ScriptRevisionReadV1> {
    return request(`/api/v1/episodes/${episodeId}/scripts/${revisionNo}`);
  },

  saveEpisodeScript(
    episodeId: string,
    baseRevision: number,
    script: ScriptV1,
    sourceMarkdown?: string,
    note?: string,
  ): Promise<ScriptRevisionReadV1> {
    return request(`/api/v1/episodes/${episodeId}/scripts`, {
      method: 'POST',
      body: jsonBody({ base_revision: baseRevision, script, source_markdown: sourceMarkdown, note }),
    });
  },

  materializeScriptPanels(
    episodeId: string,
    revisionNo: number,
    baseDocumentRevision: number,
    confirmDialogueSync = false,
  ): Promise<ScriptMaterializationResultV1> {
    return request(`/api/v1/episodes/${episodeId}/scripts/${revisionNo}/materialize`, {
      method: 'POST',
      body: jsonBody({
        base_document_revision: baseDocumentRevision,
        confirm_dialogue_sync: confirmDialogueSync,
      }),
    });
  },

  createGenerationTask(episodeId: string, payload: GenerationTaskCreateV1): Promise<GenerationTaskV1> {
    return request(`/api/v1/episodes/${episodeId}/generation-tasks`, {
      method: 'POST',
      body: jsonBody(payload),
    });
  },

  getGenerationTask(taskId: string): Promise<GenerationTaskV1> {
    return request(`/api/v1/generation-tasks/${taskId}`);
  },

  startManualGeneration(taskId: string): Promise<GenerationTaskV1> {
    return request(`/api/v1/generation-tasks/${taskId}/waiting-manual-generation`, { method: 'POST' });
  },

  importGenerationCandidate(taskId: string, assetVersionId: string): Promise<GenerationCandidateV1> {
    return request(`/api/v1/generation-tasks/${taskId}/candidates`, {
      method: 'POST',
      body: jsonBody({ asset_version_id: assetVersionId }),
    });
  },

  getGenerationCandidates(ipId: string): Promise<GenerationCandidateV1[]> {
    return request(`/api/v1/ips/${ipId}/generation-candidates`);
  },

  approveGenerationCandidate(candidateId: string): Promise<GenerationCandidateV1> {
    return request(`/api/v1/generation-candidates/${candidateId}/approve`, { method: 'POST' });
  },

  rejectGenerationCandidate(candidateId: string, reviewNote: string): Promise<GenerationCandidateV1> {
    return request(`/api/v1/generation-candidates/${candidateId}/reject`, {
      method: 'POST',
      body: jsonBody({ review_note: reviewNote }),
    });
  },

  getCodexCapabilities(): Promise<CodexCapabilityV1> {
    return request('/api/v1/codex/capabilities');
  },

  probeCodexCapabilities(): Promise<CodexCapabilityV1> {
    return request('/api/v1/codex/capabilities/probe', { method: 'POST' });
  },

  startCodexRun(taskId: string): Promise<CodexRunV1> {
    return request(`/api/v1/generation-tasks/${taskId}/codex-runs`, { method: 'POST' });
  },

  getCodexRun(runId: string): Promise<CodexRunV1> {
    return request(`/api/v1/codex-runs/${runId}`);
  },

  cancelCodexRun(runId: string): Promise<CodexRunV1> {
    return request(`/api/v1/codex-runs/${runId}/cancel`, { method: 'POST' });
  },

  getCodexPatchProposals(episodeId: string): Promise<CodexPatchProposalV1[]> {
    return request(`/api/v1/episodes/${episodeId}/codex-patches`);
  },

  proposeCodexPatch(episodeId: string, instruction: string): Promise<CodexPatchProposalV1> {
    return request(`/api/v1/episodes/${episodeId}/codex-patches`, {
      method: 'POST',
      body: jsonBody({ instruction }),
    });
  },

  approveCodexPatch(
    patchId: string,
    baseRevision: number,
    approvalId: string,
  ): Promise<CodexPatchProposalV1> {
    return request(`/api/v1/codex/patches/${patchId}/approve`, {
      method: 'POST',
      body: jsonBody({ base_revision: baseRevision, approval_id: approvalId }),
    });
  },

  rejectCodexPatch(patchId: string, reviewNote: string): Promise<CodexPatchProposalV1> {
    return request(`/api/v1/codex/patches/${patchId}/reject`, {
      method: 'POST',
      body: jsonBody({ review_note: reviewNote }),
    });
  },

  createPngExport(episodeId: string, revisionNo: number, pages: Blob[]): Promise<ExportJobReadV1> {
    const body = new FormData();
    body.set('revision_no', String(revisionNo));
    pages.forEach((page, index) => body.append('pages', page, `page-${index + 1}.png`));
    return request(`/api/v1/episodes/${episodeId}/export`, { method: 'POST', body });
  },

  async downloadExport(exportId: string): Promise<Blob> {
    const headers = new Headers();
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
    const response = await fetch(`${API_BASE_URL}/api/v1/exports/${exportId}/download`, { headers });
    if (!response.ok) {
      let message = `请求失败（${response.status}）`;
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === 'string') message = body.detail;
      } catch {
        // Keep the status-based message when the server does not return JSON.
      }
      if (response.status === 401) expireAccessToken();
      throw new ApiError(message, response.status);
    }
    return response.blob();
  },

  async getGenerationReferenceBundle(taskId: string): Promise<Blob> {
    const headers = new Headers();
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
    const response = await fetch(
      `${API_BASE_URL}/api/v1/generation-tasks/${taskId}/reference-bundle`,
      { headers },
    );
    if (!response.ok) {
      if (response.status === 401) expireAccessToken();
      throw new ApiError('无法下载生图参考包', response.status);
    }
    return response.blob();
  },
};
