import { readFileSync } from 'node:fs';
import { readFile as readFileAsync } from 'node:fs/promises';
import { resolve } from 'node:path';
import JSZip from 'jszip';
import { expect, test, type Page, type Route } from '@playwright/test';

const seed = JSON.parse(readFileSync(resolve(__dirname, 'fixtures/ip-studio-seed.json'), 'utf-8')) as any;
const pngBytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhZkAAAAASUVORK5CYII=', 'base64');

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function readPngParts(body: Buffer, contentType: string): Buffer[] {
  const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^;]+))/i);
  const boundary = boundaryMatch?.[1] ?? boundaryMatch?.[2]?.trim();
  if (!boundary) return [];
  return body.toString('latin1').split(`--${boundary}`).flatMap((part) => {
    let segment = part.replace(/^\r\n/, '').replace(/\r\n$/, '');
    const headerEnd = segment.indexOf('\r\n\r\n');
    if (headerEnd < 0 || !segment.slice(0, headerEnd).includes('name="pages"')) return [];
    segment = segment.slice(headerEnd + 4);
    return [Buffer.from(segment, 'latin1')];
  });
}

async function startWorkspace(page: Page, options: { empty?: boolean; sharedState?: any; pageCount?: number; elementCount?: number; assetVersionRegression?: boolean } = {}) {
  const state = options.sharedState ?? structuredClone(seed);
  if (options.assetVersionRegression) {
    const frozenVersion = state.assets[0];
    state.historicalAssetVersions = { [frozenVersion.asset_version_id]: frozenVersion };
    state.assetVersionLookups = [];
    state.assets[0] = {
      ...frozenVersion,
      asset_version_id: '10000000-0000-4000-8000-000000000054',
      version_no: frozenVersion.version_no + 1,
      sha256: 'd'.repeat(64),
    };
  }
  const initialVersion = {
    brand_template_version_id: state.brand_version_id,
    brand_template_id: state.brand_template_id,
    version_no: 1,
    status: 'approved',
    template: state.brand,
    derived_from_version_id: null,
    approved_at: '2026-10-14T00:00:00Z',
  };
  if (!options.sharedState) {
    state.series = [state.series];
    state.brandTemplates = [{ brand_template_id: state.brand_template_id, ip_id: state.ip.id, name: '卡仔固定外壳', versions: [initialVersion] }];
    if (options.empty) {
      state.series = [];
      state.episodes = [];
      state.documents = {};
      state.brandTemplates = [];
    }
  }
  if (options.pageCount && state.documents[state.episodes[0]?.id]?.document) {
    const saved = state.documents[state.episodes[0].id];
    const templatePage = saved.document.pages[0];
    saved.document.pages = Array.from({ length: options.pageCount }, (_, index) => ({
      ...structuredClone(templatePage),
      id: `10000000-0000-4000-8000-${String(400 + index).padStart(12, '0')}`,
      order: index + 1,
    }));
  }
  if (options.elementCount && state.documents[state.episodes[0]?.id]?.document) {
    const canvasPage = state.documents[state.episodes[0].id].document.pages[0];
    const existingCount = canvasPage.panels.reduce((count: number, panel: any) => count + panel.elements.length, 0);
    const firstPanel = canvasPage.panels[0];
    for (let index = existingCount; index < options.elementCount; index += 1) {
      firstPanel.elements.push({
        id: `10000000-0000-4000-8000-${String(500 + index).padStart(12, '0')}`,
        type: 'text',
        props: { text: `性能检查图层 ${index + 1}`, font_family: 'sans-serif', font_size: 18, font_weight: 400, color: '#242923', align: 'left', line_height: 1.3, letter_spacing: 0 },
        transform: { x: 24 + ((index - 5) % 5) * 196, y: 145 + Math.floor((index - 5) / 5) * 22, width: 180, height: 22, rotation: 0 },
        opacity: 1,
        z_index: index + 1,
        locked: false,
      });
    }
  }
  await page.route('**/api/v1/**', async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });

    if (method === 'GET' && path === '/api/v1/auth/me') return json(state.admin);
    if (method === 'GET' && path === '/api/v1/ips') return json([state.ip]);
    if (method === 'GET' && path === '/api/v1/series') return json(state.series.filter((item: any) => item.ip_id === url.searchParams.get('ip_id')));
    if (method === 'GET' && path === `/api/v1/ips/${state.ip.id}/brand-templates`) {
      return json(state.brandTemplates);
    }
    if (method === 'POST' && path === '/api/v1/series') {
      const body = request.postDataJSON() as { ip_id: string; name: string };
      const created = { id: '10000000-0000-4000-8000-000000000090', ip_id: body.ip_id, name: body.name, summary: null, created_at: '2026-10-14T00:00:00Z' };
      state.series.push(created);
      return json(created, 201);
    }
    const episodeCollection = path.match(/^\/api\/v1\/series\/([^/]+)\/episodes$/);
    if (episodeCollection && method === 'GET') return json(state.episodes.filter((item: any) => item.series_id === episodeCollection[1]));
    if (episodeCollection && method === 'POST') {
      const body = request.postDataJSON() as { number: number; title: string };
      const created = { id: '10000000-0000-4000-8000-000000000091', series_id: episodeCollection[1], number: body.number, title: body.title, status: 'draft', created_at: '2026-10-14T00:00:00Z' };
      state.episodes.push(created);
      if (state.nextEpisodeCreateGate) {
        const gate = state.nextEpisodeCreateGate as Promise<void>;
        delete state.nextEpisodeCreateGate;
        state.onEpisodeCreateStarted?.();
        await gate;
      }
      return json(created, 201);
    }
    if (method === 'POST' && path === `/api/v1/ips/${state.ip.id}/brand-templates`) {
      const body = request.postDataJSON() as { name: string; template: unknown };
      const candidate = { brand_template_version_id: state.brand_version_id, brand_template_id: state.brand_template_id, version_no: 1, status: 'candidate', template: body.template, derived_from_version_id: null, approved_at: null };
      state.brandTemplates.push({ brand_template_id: state.brand_template_id, ip_id: state.ip.id, name: body.name, versions: [candidate] });
      return json(candidate, 201);
    }
    const approvalMatch = path.match(/^\/api\/v1\/brand-template-versions\/([^/]+)\/approve$/);
    if (approvalMatch && method === 'POST') {
      const version = state.brandTemplates.flatMap((item: any) => item.versions).find((item: any) => item.brand_template_version_id === approvalMatch[1]);
      if (!version) return json({ detail: 'Brand template version not found' }, 404);
      version.status = 'approved';
      version.approved_at = '2026-10-14T00:00:00Z';
      return json(version);
    }
    const versionMatch = path.match(/^\/api\/v1\/brand-template-versions\/([^/]+)$/);
    if (versionMatch && method === 'GET') {
      const version = state.brandTemplates.flatMap((item: any) => item.versions).find((item: any) => item.brand_template_version_id === versionMatch[1]);
      return version ? json(version) : json({ detail: 'Brand template version not found' }, 404);
    }
    const scriptsMatch = path.match(/^\/api\/v1\/episodes\/([^/]+)\/scripts$/);
    if (scriptsMatch && method === 'GET') return json((state.scripts ??= {})[scriptsMatch[1]] ?? []);
    if (scriptsMatch && method === 'POST') {
      if (state.nextScriptSaveGate) {
        const gate = state.nextScriptSaveGate as Promise<void>;
        delete state.nextScriptSaveGate;
        state.onScriptSaveStarted?.();
        await gate;
      }
      const revisions = (state.scripts ??= {})[scriptsMatch[1]] ??= [];
      const body = request.postDataJSON() as { base_revision: number; source_markdown: string; script: any };
      if (body.base_revision !== revisions.length) return json({ detail: 'Script revision changed' }, 409);
      const saved = {
        revision_id: `10000000-0000-4000-8000-${String(100 + revisions.length).padStart(12, '0')}`,
        revision_no: revisions.length + 1,
        source_markdown: body.source_markdown,
        script: body.script,
        note: null,
        created_at: '2026-10-14T00:00:00Z',
      };
      revisions.push(saved);
      return json(saved, 201);
    }
    const materializeMatch = path.match(/^\/api\/v1\/episodes\/([^/]+)\/scripts\/(\d+)\/materialize$/);
    if (materializeMatch && method === 'POST') {
      if (state.nextMaterializeGate) {
        const gate = state.nextMaterializeGate as Promise<void>;
        delete state.nextMaterializeGate;
        state.onMaterializeStarted?.();
        await gate;
      }
      const [, episodeId, revisionNo] = materializeMatch;
      const scriptRevision = (state.scripts?.[episodeId] ?? []).find((item: any) => item.revision_no === Number(revisionNo));
      if (!scriptRevision) return json({ detail: 'Script revision not found' }, 404);
      const body = request.postDataJSON() as { base_document_revision: number; confirm_dialogue_sync: boolean };
      let panelOrder = 0;
      const panels = scriptRevision.script.scenes.flatMap((scene: any) => {
        const dialogues = new Map(scene.dialogues.map((dialogue: any) => [dialogue.dialogue_id, dialogue]));
        return scene.panels.map((panel: any) => ({
          panel_id: panel.action_id,
          panel_order: ++panelOrder,
          scene_id: scene.scene_id,
          scene_name: scene.name,
          location: scene.location,
          time: scene.time,
          action: panel.action,
          shot_type: panel.shot_type,
          character_version_ids: panel.character_version_ids,
          background_asset_version_id: panel.background_asset_version_id,
          no_text_prompt: panel.no_text_prompt,
          dialogues: panel.dialogue_ids.map((id: string) => dialogues.get(id)),
        }));
      });
      const current = state.documents[episodeId];
      const plannedChat = panels.flatMap((panel: any) => panel.dialogues).find((dialogue: any) => dialogue?.kind === 'chat_message');
      const firstChat = current?.document.pages.flatMap((canvasPage: any) => canvasPage.panels)
        .flatMap((canvasPanel: any) => canvasPanel.elements)
        .find((element: any) => element.type === 'chat_message');
      const dialogueChanges = plannedChat && firstChat && plannedChat.text !== firstChat.props.text
        ? [{ panel_order: 1, element_id: firstChat.id, old_text: firstChat.props.text, new_text: plannedChat.text }]
        : [];
      if (dialogueChanges.length > 0 && !body.confirm_dialogue_sync) {
        return json({ detail: { message: '剧本对白与画布中已有聊天文字不同', dialogue_changes: dialogueChanges } }, 409);
      }
      if (dialogueChanges.length > 0 && current) {
        if (body.base_document_revision !== current.revision) return json({ detail: 'Document revision changed' }, 409);
        const document = structuredClone(current.document);
        const changeById = new Map(dialogueChanges.map((change: any) => [change.element_id, change.new_text]));
        for (const canvasPage of document.pages) {
          for (const canvasPanel of canvasPage.panels) {
            for (const element of canvasPanel.elements) {
              if (changeById.has(element.id)) element.props.text = changeById.get(element.id);
            }
          }
        }
        const revision = current.revision + 1;
        document.revision = revision;
        state.documents[episodeId] = { revision, document };
      }
      const documentRevision = state.documents[episodeId]?.revision ?? 0;
      return json({ script_revision_no: Number(revisionNo), document_revision: documentRevision, panels, synced_dialogue_count: body.confirm_dialogue_sync ? dialogueChanges.length : 0, dialogue_changes: dialogueChanges });
    }
    const taskCollection = path.match(/^\/api\/v1\/episodes\/([^/]+)\/generation-tasks$/);
    if (taskCollection && method === 'POST') {
      if (state.nextGenerationTaskGate) {
        const gate = state.nextGenerationTaskGate as Promise<void>;
        delete state.nextGenerationTaskGate;
        state.onGenerationTaskStarted?.();
        await gate;
      }
      const episodeId = taskCollection[1];
      const body = request.postDataJSON() as { script_revision_no: number; panel_id: string };
      const scriptRevision = (state.scripts?.[episodeId] ?? []).find((item: any) => item.revision_no === body.script_revision_no);
      if (!scriptRevision) return json({ detail: 'Script revision not found' }, 404);
      const panelPlan = scriptRevision.script.scenes.flatMap((scene: any) => scene.panels).find((panel: any) => panel.action_id === body.panel_id);
      if (!panelPlan) return json({ detail: 'Panel not found' }, 404);
      const task = {
        task_id: '10000000-0000-4000-8000-000000000098',
        episode_id: episodeId,
        script_revision_id: scriptRevision.revision_id,
        script_revision_no: body.script_revision_no,
        panel_id: body.panel_id,
        mode: 'chatgpt_web',
        status: 'prepared',
        prompt_snapshot: { schema_version: '1.0', text: `${panelPlan.action}\n${panelPlan.no_text_prompt}`, panel: panelPlan, locked_version_ids: [] },
        reference_snapshot: [],
        reference_bundle_url: `/api/v1/generation-tasks/10000000-0000-4000-8000-000000000098/reference-bundle`,
        created_at: '2026-10-14T00:00:00Z',
      };
      state.generationTask = task;
      return json(task, 201);
    }
    const startManualMatch = path.match(/^\/api\/v1\/generation-tasks\/([^/]+)\/waiting-manual-generation$/);
    if (startManualMatch && method === 'POST' && state.generationTask?.task_id === startManualMatch[1]) {
      state.generationTask.status = 'waiting_manual_generation';
      return json(state.generationTask);
    }
    if (method === 'GET' && path.endsWith('/reference-bundle')) {
      return route.fulfill({ status: 200, contentType: 'application/zip', body: Buffer.alloc(0) });
    }
    const candidatesMatch = path.match(/^\/api\/v1\/ips\/([^/]+)\/generation-candidates$/);
    if (candidatesMatch && method === 'GET') return json(state.candidates ?? []);
    if (method === 'GET' && path === '/api/v1/codex/capabilities') {
      return json({ status: 'unsupported', reason: '当前 Codex 不支持 ImageGen；可以使用 ChatGPT Web 人工生成。', codex_path: null, codex_version: null, app_server_available: false, image_generation_advertised: false, e2e_verified: false, checked_at: '2026-10-14T00:00:00Z' });
    }
    const codexPatchesMatch = path.match(/^\/api\/v1\/episodes\/([^/]+)\/codex-patches$/);
    if (codexPatchesMatch && method === 'GET') return json([]);
    if (method === 'POST' && path === '/api/v1/assets/upload') {
      const idSuffix = String(200 + state.assets.length).padStart(12, '0');
      const asset = {
        asset_id: `10000000-0000-4000-8000-${idSuffix}`,
        asset_version_id: `10000000-0000-4000-8000-${String(Number(idSuffix) + 1).padStart(12, '0')}`,
        workspace_id: state.admin.workspace_id,
        owner_ip_id: state.ip.id,
        type: 'composite_panel',
        name: '人工生图结果',
        status: 'candidate',
        source_type: 'uploaded',
        version_no: 1,
        sha256: 'c'.repeat(64),
        mime: 'image/png',
        byte_size: pngBytes.length,
        width: 1,
        height: 1,
        alpha: true,
        created_at: '2026-10-14T00:00:00Z',
      };
      state.assets.push(asset);
      return json(asset, 201);
    }
    const taskCandidatesMatch = path.match(/^\/api\/v1\/generation-tasks\/([^/]+)\/candidates$/);
    if (taskCandidatesMatch && method === 'POST') {
      const body = request.postDataJSON() as { asset_version_id: string };
      const asset = state.assets.find((item: any) => item.asset_version_id === body.asset_version_id);
      if (!asset || !state.generationTask) return json({ detail: 'Candidate asset not found' }, 404);
      const candidate = {
        candidate_id: '10000000-0000-4000-8000-000000000099',
        task_id: taskCandidatesMatch[1],
        panel_id: state.generationTask.panel_id,
        asset_id: asset.asset_id,
        asset_version_id: asset.asset_version_id,
        asset_name: asset.name,
        asset_type: asset.type,
        version_no: 1,
        mime: asset.mime,
        sha256: asset.sha256,
        byte_size: asset.byte_size,
        width: asset.width,
        height: asset.height,
        status: 'pending_review',
        created_at: '2026-10-14T00:00:00Z',
        reviewed_at: null,
        reviewed_by_user_id: null,
        review_note: null,
      };
      state.candidates = [...(state.candidates ?? []), candidate];
      return json(candidate, 201);
    }
    const candidateReviewMatch = path.match(/^\/api\/v1\/generation-candidates\/([^/]+)\/(approve|reject)$/);
    if (candidateReviewMatch && method === 'POST') {
      const candidate = (state.candidates ?? []).find((item: any) => item.candidate_id === candidateReviewMatch[1]);
      if (!candidate) return json({ detail: 'Candidate not found' }, 404);
      candidate.status = candidateReviewMatch[2] === 'approve' ? 'approved' : 'rejected';
      candidate.reviewed_at = '2026-10-14T00:00:00Z';
      candidate.reviewed_by_user_id = state.admin.id;
      return json(candidate);
    }
    const assetVersionMatch = path.match(/^\/api\/v1\/assets\/versions\/([^/]+)$/);
    if (method === 'GET' && assetVersionMatch) {
      state.assetVersionLookups?.push(assetVersionMatch[1]);
      const historical = state.historicalAssetVersions?.[assetVersionMatch[1]];
      return historical ? json(historical) : json({ detail: 'Asset version not found' }, 404);
    }
    if (method === 'GET' && path === '/api/v1/assets') return json(state.assets);
    if (method === 'GET' && path === `/api/v1/series/${state.series.id}/episodes`) return json(state.episodes);
    if (method === 'GET' && path.startsWith('/api/v1/assets/') && path.endsWith('/content')) {
      return route.fulfill({ status: 200, contentType: 'image/png', body: pngBytes });
    }
    const episodeMatch = path.match(/^\/api\/v1\/episodes\/([^/]+)\/document$/);
    if (episodeMatch && method === 'GET') return json(state.documents[episodeMatch[1]] ?? { revision: 0, document: null });
    if (episodeMatch && method === 'PUT') {
      const episodeId = episodeMatch[1];
      const body = request.postDataJSON() as { base_revision: number; document: Record<string, unknown> };
      if (state.nextDocumentSaveGate) {
        const gate = state.nextDocumentSaveGate as Promise<void>;
        delete state.nextDocumentSaveGate;
        state.onDocumentSaveStarted?.();
        await gate;
      }
      const latest = state.documents[episodeId] ?? { revision: 0, document: null };
      if (body.base_revision !== latest.revision) return json({ detail: 'Document revision changed; reload the latest version' }, 409);
      const revision = latest.revision + 1;
      const document = { ...body.document, revision };
      state.documents[episodeId] = { revision, document };
      return json({ revision, document });
    }
    if (method === 'POST' && path.match(/^\/api\/v1\/episodes\/([^/]+)\/export$/)) {
      const exportPathMatch = path.match(/^\/api\/v1\/episodes\/([^/]+)\/export$/)!;
      const uploadedPages = readPngParts(request.postDataBuffer() ?? Buffer.alloc(0), request.headers()['content-type'] ?? '');
      const pageCount = uploadedPages.length;
      state.pngExportPageCount = pageCount;
      state.exportedPngDimensions = uploadedPages.map((buffer) => buffer.length >= 24 && buffer.subarray(1, 4).toString() === 'PNG'
        ? [buffer.readUInt32BE(16), buffer.readUInt32BE(20)]
        : null);
      state.exportedPngNames = uploadedPages.map((_, index) => `page-${index + 1}.png`);
      return json({
        id: '10000000-0000-4000-8000-000000000097',
        episode_id: exportPathMatch[1],
        revision_no: state.documents[exportPathMatch[1]]?.revision,
        format: 'png_zip',
        status: 'complete',
        page_count: pageCount,
        warnings: [],
        download_url: '/api/v1/exports/10000000-0000-4000-8000-000000000097/download',
        created_at: '2026-10-14T00:00:00Z',
      }, 201);
    }
    if (method === 'GET' && path === '/api/v1/exports/10000000-0000-4000-8000-000000000097/download') {
      const archive = new JSZip();
      for (let index = 0; index < (state.pngExportPageCount ?? 0); index += 1) {
        archive.file(`pages/page-${String(index + 1).padStart(3, '0')}.png`, pngBytes);
      }
      return route.fulfill({ status: 200, contentType: 'application/zip', body: await archive.generateAsync({ type: 'nodebuffer' }) });
    }
    return json({ detail: `Unhandled E2E request: ${method} ${path}` }, 501);
  });
  await page.addInitScript(() => window.sessionStorage.setItem('ip-studio-access-token', 'e2e-token'));
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: state.ip.name })).toBeVisible();
  return state;
}

test('reopens frozen canvas image versions when the asset library has newer versions', async ({ page }) => {
  const state = await startWorkspace(page, { assetVersionRegression: true });
  await page.getByRole('tab', { name: '漫画工作台' }).click();

  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  await expect.poll(() => state.assetVersionLookups).toContain('10000000-0000-4000-8000-000000000051');
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('warns before leaving the comic workspace with unsaved edits', async ({ page }) => {
  await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  const title = page.getByLabel('页面标题');
  await title.fill('未保存的新标题');
  const summary = page.getByLabel('故事概要');
  await summary.fill('尚未保存的剧本草稿');

  page.once('dialog', (dialog) => dialog.dismiss());
  await page.getByRole('tab', { name: '素材库' }).click();
  await expect(page.getByRole('tab', { name: '漫画工作台' })).toHaveAttribute('aria-selected', 'true');
  await expect(title).toHaveValue('未保存的新标题');
  await expect(summary).toHaveValue('尚未保存的剧本草稿');

  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('tab', { name: '素材库' }).click();
  await expect(page.getByRole('tab', { name: '素材库' })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByLabel('页面标题')).toHaveValue('在吗？');
  await expect(page.getByLabel('故事概要')).toHaveValue('');
});

test('confirms before switching episodes with an unsaved script draft', async ({ page }) => {
  await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  const episodePicker = page.getByLabel('选择单集');
  const summary = page.getByLabel('故事概要');
  await summary.fill('只存在于剧本编辑器中的草稿');

  page.once('dialog', (dialog) => dialog.dismiss());
  await episodePicker.selectOption(seed.episodes[1].id);
  await expect(episodePicker).toHaveValue(seed.episodes[0].id);
  await expect(summary).toHaveValue('只存在于剧本编辑器中的草稿');

  page.once('dialog', (dialog) => dialog.accept());
  await episodePicker.selectOption(seed.episodes[1].id);
  await expect(episodePicker).toHaveValue(seed.episodes[1].id);
  await expect(summary).toHaveValue('');
});

test('prevents episode switching while a script revision is being saved', async ({ page }) => {
  const state = await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await page.getByLabel('故事概要').fill('待保存的剧本修订');
  const saveGate = deferred<void>();
  const saveStarted = deferred<void>();
  state.nextScriptSaveGate = saveGate.promise;
  state.onScriptSaveStarted = saveStarted.resolve;

  await page.getByRole('button', { name: '保存为新修订' }).click();
  await saveStarted.promise;
  await expect(page.getByLabel('选择单集')).toBeDisabled();
  saveGate.resolve();
  await expect(page.getByText('SCRIPT REVISION · V1')).toBeVisible();
  await expect(page.getByLabel('选择单集')).toBeEnabled();
});

test('locks the current canvas while a new episode is being created', async ({ page }) => {
  const state = await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  const createGate = deferred<void>();
  const createStarted = deferred<void>();
  state.nextEpisodeCreateGate = createGate.promise;
  state.onEpisodeCreateStarted = createStarted.resolve;

  await page.getByLabel('新单集标题').fill('创建期间的下一集');
  await page.getByRole('button', { name: '创建单集' }).click();
  await createStarted.promise;

  await expect(page.locator('.comic-workspace')).toHaveAttribute('inert', '');
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  createGate.resolve();

  await expect(page.getByRole('heading', { name: 'EP.03 · 创建期间的下一集' })).toBeVisible();
  await expect(page.locator('.comic-workspace')).not.toHaveAttribute('inert', '');
});

test('locks the selected episode and panel while a generation task is being created', async ({ page }) => {
  const state = await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await page.getByLabel('分集标题').fill('在吗？·任务版');
  await page.getByLabel('剧情动作 · 场景 1').fill('朋友发来一条消息，卡仔看向手机。');
  await page.getByRole('button', { name: '＋ 添加画格卡' }).click();
  await page.getByLabel('分镜动作').fill('任务创建期间保持目标分镜不变。');
  await page.getByRole('button', { name: '保存为新修订' }).click();
  await expect(page.getByText('SCRIPT REVISION · V1')).toBeVisible();
  await page.getByRole('button', { name: '从剧本生成分镜卡' }).click();
  const taskGate = deferred<void>();
  const taskStarted = deferred<void>();
  state.nextGenerationTaskGate = taskGate.promise;
  state.onGenerationTaskStarted = taskStarted.resolve;

  await page.getByRole('button', { name: '准备 ChatGPT Web 生图任务' }).click();
  await taskStarted.promise;
  await expect(page.locator('.comic-workspace')).toHaveAttribute('inert', '');
  await expect(page.getByLabel('生图目标分镜卡')).toBeDisabled();
  taskGate.resolve();

  await expect(page.getByRole('heading', { name: '单格生图任务' })).toBeVisible();
  await expect(page.locator('.comic-workspace')).not.toHaveAttribute('inert', '');
});

test('clears canvas undo history after confirmed script dialogue sync', async ({ page }) => {
  const state = await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();

  await page.getByLabel('页面标题').fill('已保存、但历史仍可撤销');
  await page.getByRole('button', { name: '保存画布' }).click();
  const toolbar = page.getByRole('toolbar', { name: '画布工具' });
  await expect(toolbar.getByText('已保存')).toBeVisible();
  await expect(toolbar.getByRole('button', { name: '撤销' })).toBeEnabled();

  const scene = page.getByRole('group', { name: '场景 1' });
  await scene.getByRole('button', { name: '＋ 添加对白' }).click();
  await scene.getByLabel('说话人').fill('朋友');
  await scene.getByLabel('对白类型 · 朋友').selectOption('chat_message');
  await scene.getByLabel('对白 · 朋友').fill('脚本更新后的对白');
  await scene.getByRole('button', { name: '＋ 添加画格卡' }).click();
  await scene.getByLabel('分镜动作').fill('朋友发来新消息');
  await page.getByRole('button', { name: '保存为新修订' }).click();
  await expect(page.getByText('SCRIPT REVISION · V1')).toBeVisible();

  await page.getByRole('button', { name: '从剧本生成分镜卡' }).click();
  const preview = page.getByRole('alertdialog', { name: '确认同步画布对白' });
  await expect(preview).toContainText('在吗？');
  await expect(preview).toContainText('脚本更新后的对白');
  const materializeGate = deferred<void>();
  const materializeStarted = deferred<void>();
  state.nextMaterializeGate = materializeGate.promise;
  state.onMaterializeStarted = materializeStarted.resolve;
  await preview.getByRole('button', { name: '确认并同步对白' }).click();
  await materializeStarted.promise;
  await expect(page.locator('.comic-workspace')).toHaveAttribute('inert', '');
  materializeGate.resolve();

  await expect(page.getByRole('status').filter({ hasText: '已同步 1 条对白' })).toBeVisible();
  await expect(page.locator('.comic-workspace')).not.toHaveAttribute('inert', '');
  const syncedMessage = state.documents[state.episodes[0].id].document.pages.flatMap((canvasPage: any) => canvasPage.panels)
    .flatMap((canvasPanel: any) => canvasPanel.elements)
    .find((element: any) => element.type === 'chat_message' && element.props.text === '脚本更新后的对白');
  expect(syncedMessage).toBeDefined();
  await expect(toolbar.getByRole('button', { name: '撤销' })).toBeDisabled();
  await expect(toolbar.getByRole('button', { name: '重做' })).toBeDisabled();
});

test('EP01 dialogue direction, scoped edits, EP02 shared brand, and editable PPTX export', async ({ page }, testInfo) => {
  const state = await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();

  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  const ep01 = state.documents[state.episodes[0].id].document;
  const chat = ep01.pages[0].panels[0].elements.filter((element: any) => element.type === 'chat_message');
  expect(chat[0].transform.x).toBeLessThan(chat[1].transform.x);
  expect(chat.map((message: any) => message.props.text)).toEqual(['在吗？', '不在。']);

  const original = structuredClone(ep01);
  const layerRows = page.locator('.editor-layer-row');
  await layerRows.nth(0).click();
  await layerRows.nth(1).click({ modifiers: ['Shift'] });
  await expect(page.getByText('已选择 2 个图层', { exact: true })).toBeVisible();
  await page.getByLabel('整体水平位移').fill('10');
  await page.getByLabel('整体垂直位移').fill('5');
  await page.getByRole('button', { name: '整体移动所选图层' }).click();
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.getByRole('toolbar', { name: '画布工具' }).getByText('已保存')).toBeVisible();
  const movedChats = state.documents[state.episodes[0].id].document.pages[0].panels[0].elements
    .filter((element: any) => element.type === 'chat_message');
  expect(movedChats.map((message: any) => message.transform.x)).toEqual(chat.map((message: any) => message.transform.x + 10));

  const toolbar = page.getByRole('toolbar', { name: '画布工具' });
  await toolbar.getByRole('button', { name: '撤销' }).click();
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.getByRole('toolbar', { name: '画布工具' }).getByText('已保存')).toBeVisible();
  const restoredChats = state.documents[state.episodes[0].id].document.pages[0].panels[0].elements
    .filter((element: any) => element.type === 'chat_message');
  expect(restoredChats.map((message: any) => message.transform)).toEqual(chat.map((message: any) => message.transform));

  await page.getByRole('button', { name: /image.*格 2/i }).click();
  await page.getByLabel('替换单格图片').selectOption(state.assets[1].asset_version_id);
  await page.getByRole('button', { name: /text.*格 4/i }).click();
  const textEditor = page.getByLabel('图层文字内容');
  for (let change = 1; change <= 10; change += 1) {
    await textEditor.fill(`会议状态第${change}次修改`);
  }
  await toolbar.getByRole('button', { name: '撤销' }).click();
  await expect(textEditor).toHaveValue('会议状态第9次修改');
  await toolbar.getByRole('button', { name: '重做' }).click();
  await expect(textEditor).toHaveValue('会议状态第10次修改');
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.getByRole('toolbar', { name: '画布工具' }).getByText('已保存')).toBeVisible();

  const savedEp01 = state.documents[state.episodes[0].id].document;
  const savedPanels = savedEp01.pages[0].panels;
  expect(savedEp01.brand_template_version_id).toBe(state.brand_version_id);
  expect(savedPanels[0].elements).toEqual(original.pages[0].panels[0].elements);
  expect(savedPanels[1].elements[0].asset_version_id).toBe(state.assets[1].asset_version_id);
  expect(savedPanels[1].elements[0].transform).toEqual(original.pages[0].panels[1].elements[0].transform);
  expect(savedPanels[2].elements).toEqual(original.pages[0].panels[2].elements);
  expect(savedPanels[3].elements[0].props.text).toBe('会议状态第10次修改');
  expect(savedPanels[3].elements[0].transform).toEqual(original.pages[0].panels[3].elements[0].transform);

  await page.reload();
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  await page.getByRole('button', { name: /text.*格 4/i }).click();
  await expect(page.getByLabel('图层文字内容')).toHaveValue('会议状态第10次修改');

  await page.getByLabel('选择单集').selectOption(state.episodes[1].id);
  await expect(page.getByRole('heading', { name: 'EP.02 · 今天又加班' })).toBeVisible();
  expect(state.documents[state.episodes[1].id].document.brand_template_version_id).toBe(state.brand_version_id);
  expect(state.documents[state.episodes[1].id].document.dynamic_fields.title).not.toBe(savedEp01.dynamic_fields.title);

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出可编辑 PPTX' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('episode-r1-editable.pptx');
  const archive = await JSZip.loadAsync(await readFileAsync((await download.path())!));
  const slideXml = await archive.file('ppt/slides/slide1.xml')?.async('string');
  expect((slideXml?.match(/<p:pic\b/g) ?? []).length).toBe(2);
  expect((slideXml?.match(/<p:sp\b/g) ?? []).length).toBeGreaterThan(8);
  expect(slideXml).toContain('还没下班？');
  expect(slideXml).toContain('我去开会。');

  await page.screenshot({ path: testInfo.outputPath('ep02-editor.png'), fullPage: true });
});

test('an empty IP can create a series, approved starter brand, episode, and first saved canvas', async ({ page }) => {
  const state = await startWorkspace(page, { empty: true });
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await page.getByLabel('系列名称').fill('人间卡顿局日常');
  await page.getByRole('button', { name: '创建系列' }).click();
  await expect(page.getByLabel('选择系列')).toHaveValue('10000000-0000-4000-8000-000000000090');
  await page.getByLabel('新单集标题').fill('第一次加班');
  await page.getByRole('button', { name: '创建单集' }).click();
  await page.getByRole('button', { name: '建立并批准默认外壳' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 第一次加班' })).toBeVisible();
  expect(state.brandTemplates[0].versions[0].status).toBe('approved');
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.getByRole('toolbar', { name: '画布工具' }).getByText('已保存')).toBeVisible();
  const createdEpisode = state.episodes[0];
  expect(state.documents[createdEpisode.id].revision).toBe(1);
  expect(state.documents[createdEpisode.id].document.brand_template_version_id).toBe(state.brand_version_id);
});

test('two editors use revision CAS and the stale tab cannot overwrite the winner', async ({ page }) => {
  const state = await startWorkspace(page);
  const secondTab = await page.context().newPage();
  await startWorkspace(secondTab, { sharedState: state });
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await secondTab.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  await expect(secondTab.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();

  await page.getByLabel('页面标题').fill('第一次保存成功');
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.getByRole('toolbar', { name: '画布工具' }).getByText('已保存')).toBeVisible();

  await secondTab.getByLabel('页面标题').fill('过期页面不应覆盖');
  await secondTab.getByRole('button', { name: '保存画布' }).click();
  await expect(secondTab.getByRole('alert')).toContainText('Document revision changed');
  expect(state.documents[state.episodes[0].id].revision).toBe(2);
  expect(state.documents[state.episodes[0].id].document.dynamic_fields.title).toBe('第一次保存成功');
  await secondTab.getByRole('button', { name: '重新加载服务器版本' }).click();
  await expect(secondTab.getByLabel('页面标题')).toHaveValue('第一次保存成功');
});

test('editing during a pending save stays dirty and can be saved at the returned revision', async ({ page }) => {
  const state = await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await page.getByRole('button', { name: /text.*格 4/i }).click();
  const editor = page.getByLabel('图层文字内容');
  await editor.fill('请求开始时的文本');

  const saveStarted = deferred<void>();
  const releaseSave = deferred<void>();
  state.nextDocumentSaveGate = releaseSave.promise;
  state.onDocumentSaveStarted = () => saveStarted.resolve();
  await page.getByRole('button', { name: '保存画布' }).click();
  await saveStarted.promise;
  await editor.fill('保存期间的新文本');
  releaseSave.resolve();

  await expect(page.locator('.comic-save-bar')).toContainText('有未保存更改');
  expect(state.documents[state.episodes[0].id].revision).toBe(2);
  expect(state.documents[state.episodes[0].id].document.pages[0].panels[3].elements[0].props.text).toBe('请求开始时的文本');
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.locator('.comic-save-bar')).toContainText('已保存');
  expect(state.documents[state.episodes[0].id].revision).toBe(3);
  expect(state.documents[state.episodes[0].id].document.pages[0].panels[3].elements[0].props.text).toBe('保存期间的新文本');
});

test('long Chinese copy shows a visible overflow warning before saving', async ({ page }) => {
  await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  await page.getByRole('button', { name: /text.*格 4/i }).click();
  await page.getByLabel('图层文字内容').fill('加班'.repeat(80));
  await expect(page.getByRole('alert')).toContainText('文字可能超出文本框');
});

test('production workflow keeps ChatGPT Web generation and candidate approval available', async ({ page }) => {
  await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  await expect(page.getByText('剧本与生图工作流')).toBeVisible();

  await page.getByLabel('分集标题').fill('在吗？·剧本版');
  await page.getByLabel('剧情动作 · 场景 1').fill('朋友发来一条消息，卡仔看向手机。');
  await page.getByRole('button', { name: '＋ 添加画格卡' }).click();
  await page.getByLabel('分镜动作').fill('手机屏幕亮起，朋友询问卡仔是否在线。');
  await page.getByRole('button', { name: '保存为新修订' }).click();
  await expect(page.getByText('SCRIPT REVISION · V1')).toBeVisible();
  await page.getByRole('button', { name: '从剧本生成分镜卡' }).click();
  await expect(page.getByRole('option', { name: /手机屏幕亮起/ })).toHaveCount(1);
  await page.getByRole('button', { name: '准备 ChatGPT Web 生图任务' }).click();
  await expect(page.getByRole('heading', { name: '单格生图任务' })).toBeVisible();
  await expect(page.getByText(/不会访问 ChatGPT 私有接口/)).toBeVisible();
  await page.getByRole('button', { name: '我已在 ChatGPT Web 开始生成' }).click();
  await expect(page.getByText('人工生成中', { exact: true })).toBeVisible();

  await page.getByLabel('导入候选图片').setInputFiles({
    name: 'manual-result.png',
    mimeType: 'image/png',
    buffer: pngBytes,
  });
  await expect(page.getByText('已导入为待审核候选；正式画格保持不变。')).toBeVisible();
  await expect(page.getByRole('heading', { name: '候选素材审核' })).toBeVisible();
  await page.getByRole('button', { name: /批准并加入可复用素材/ }).click();
  await expect(page.getByText(/已加入同 IP 的批准素材库/)).toBeVisible();
});

test('ten-page PNG export preserves page count and ordered image files', async ({ page }) => {
  const state = await startWorkspace(page, { pageCount: 10 });
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  await expect(page.getByText('10 页 · revision 1')).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出 PNG 图组' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('episode-r1-pages.zip');
  expect(state.pngExportPageCount).toBe(10);
  expect(state.exportedPngDimensions).toEqual(Array.from({ length: 10 }, () => [1080, 1440]));
  const archive = await JSZip.loadAsync(await readFileAsync((await download.path())!));
  const pageNames = Object.keys(archive.files).filter((name) => name.endsWith('.png'));
  expect(pageNames).toHaveLength(10);
  expect(pageNames).toEqual(Array.from({ length: 10 }, (_, index) => `pages/page-${String(index + 1).padStart(3, '0')}.png`));
});

test('thirty canvas elements remain selectable and editable without AI services', async ({ page }) => {
  const state = await startWorkspace(page, { elementCount: 30 });
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  const layerRows = page.locator('.editor-layer-row');
  await expect(layerRows).toHaveCount(30);
  await layerRows.nth(2).click();
  await page.getByLabel('图层文字内容').fill('三十图层仍可正常编辑');
  await expect(page.getByLabel('图层文字内容')).toHaveValue('三十图层仍可正常编辑');
  await expect(page.locator('.comic-save-bar').getByRole('status')).toContainText('有未保存更改');
  await layerRows.nth(3).click({ modifiers: ['Shift'] });
  await page.getByLabel('整体水平位移').fill('10');
  await page.getByLabel('整体垂直位移').fill('5');
  await page.getByRole('button', { name: '整体移动所选图层' }).click();
  const target = state.documents[state.episodes[0].id].document.pages[0].panels[0].elements[2];
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.locator('.comic-save-bar').getByRole('status')).toContainText('已保存');
  const savedElement = state.documents[state.episodes[0].id].document.pages[0].panels[0].elements
    .find((element: any) => element.id === target.id);
  expect(savedElement.transform.x).toBe(target.transform.x + 10);
  expect(savedElement.transform.y).toBe(target.transform.y + 5);
});

test('dragging one selected canvas element moves its selected siblings by the same distance', async ({ page }) => {
  const state = await startWorkspace(page);
  await page.getByRole('tab', { name: '漫画工作台' }).click();
  await expect(page.getByRole('heading', { name: 'EP.01 · 在吗？' })).toBeVisible();
  await expect(page.getByRole('form', { name: '结构化剧本编辑器' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '单格生图' })).toBeVisible();
  const layerRows = page.locator('.editor-layer-row');
  await layerRows.nth(0).click();
  await layerRows.nth(1).click({ modifiers: ['Shift'] });
  await expect(page.getByText('已选择 2 个图层', { exact: true })).toBeVisible();

  const stage = page.locator('.canvas-stage-transform');
  await stage.scrollIntoViewIfNeeded();
  await page.evaluate(async () => {
    const stageTop = document.querySelector('.canvas-stage-transform')?.getBoundingClientRect().top;
    if (stageTop !== undefined) {
      document.documentElement.style.scrollBehavior = 'auto';
      window.scrollTo(0, window.scrollY + stageTop - 160);
    }
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  });
  const box = await stage.boundingBox();
  if (!box) throw new Error('Canvas stage is not visible');
  const start = { x: box.x + (48 + 24 + 180) * 0.7, y: box.y + (48 + 32 + 52) * 0.7 };
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + 14, start.y + 7, { steps: 4 });
  await page.mouse.up();
  await expect(page.getByRole('button', { name: '保存画布' })).toBeEnabled();
  await page.getByRole('button', { name: '保存画布' }).click();
  await expect(page.getByRole('toolbar', { name: '画布工具' }).getByText('已保存')).toBeVisible();

  const moved = state.documents[state.episodes[0].id].document.pages[0].panels[0].elements;
  const first = moved.find((element: any) => element.id === '10000000-0000-4000-8000-000000000070');
  const second = moved.find((element: any) => element.id === '10000000-0000-4000-8000-000000000072');
  expect(first.transform.x - 24).toBeCloseTo(20, 0);
  expect(first.transform.y - 32).toBeCloseTo(10, 0);
  expect(second.transform.x - 544).toBeCloseTo(20, 0);
  expect(second.transform.y - 142).toBeCloseTo(10, 0);
});
