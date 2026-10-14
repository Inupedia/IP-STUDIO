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
import type { ScriptMaterializationResultV1, ScriptRevisionReadV1, ScriptV1 } from '@ip-studio/contracts/script';

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
};
