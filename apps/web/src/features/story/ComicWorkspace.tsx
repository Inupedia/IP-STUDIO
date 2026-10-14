import { lazy, Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { getLayout } from '@ip-studio/contracts/layout';
import { CanvasDocumentV1Schema, type CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { AssetVersion, IP } from '@ip-studio/contracts/domain';
import { ScriptV1Schema, type ScriptMaterializationResultV1, type ScriptRevisionReadV1, type ScriptV1, type StoryboardPanelV1 } from '@ip-studio/contracts/script';
import type { GenerationTaskV1 } from '@ip-studio/contracts/generation';
import { ComicEditor } from '../editor/ComicEditor';
import { applyCanvasCommand, type CanvasCommand } from '../editor/commands';
import type { ScriptSavePayload } from '../production/ScriptEditor';
import type { EpisodeReadV1, SeriesReadV1 } from '../../lib/api';
import { api, type BrandTemplateReadV1, type BrandTemplateVersionReadV1 } from '../../lib/api';

const ScriptEditor = lazy(() => import('../production/ScriptEditor').then((module) => ({ default: module.ScriptEditor })));
const Storyboard = lazy(() => import('../production/Storyboard').then((module) => ({ default: module.Storyboard })));
const GenerationTaskCard = lazy(() => import('../production/GenerationTaskCard').then((module) => ({ default: module.GenerationTaskCard })));
const ImportAssetDropzone = lazy(() => import('../production/ImportAssetDropzone').then((module) => ({ default: module.ImportAssetDropzone })));
const CandidateReview = lazy(() => import('../production/CandidateReview').then((module) => ({ default: module.CandidateReview })));
const CodexAssistant = lazy(() => import('../codex/CodexAssistant').then((module) => ({ default: module.CodexAssistant })));

function starterBrand(): BrandTemplateV1 {
  return {
    schema_version: '1.0',
    width: 1080,
    height: 1440,
    locked_elements: [
      { id: 'canvas-background', kind: 'background', locked: true, x: 0, y: 0, width: 1080, height: 1440, fill: '#f4f0e8', opacity: 1 },
      { id: 'brand-mark', kind: 'logo', locked: true, x: 48, y: 40, width: 120, height: 60, fill: '#243a2d', opacity: 1 },
      { id: 'brand-footer', kind: 'footer', locked: true, x: 48, y: 1380, width: 984, height: 24, fill: '#ded9ce', opacity: 1 },
    ],
    dynamic_slots: {
      title: { x: 180, y: 40, width: 700, height: 100, font_family: 'sans-serif', font_size: 48, color: '#243a2d', align: 'center' },
      episode_number: { x: 900, y: 48, width: 120, height: 52, font_family: 'sans-serif', font_size: 28, color: '#243a2d', align: 'right' },
    },
  };
}

function makeBlankDocument(
  episode: EpisodeReadV1,
  brandVersion: BrandTemplateVersionReadV1,
  defaultStyleVersionId: string | null,
): CanvasDocumentV1 {
  const brand = brandVersion.template;
  const layout = getLayout('four', brand.width, brand.height);
  return CanvasDocumentV1Schema.parse({
    schema_version: '1.0',
    episode_id: episode.id,
    revision: 0,
    style_version_id: defaultStyleVersionId,
    brand_template_version_id: brandVersion.brand_template_version_id,
    dynamic_fields: {
      title: episode.title,
      episode_number: `EP.${String(episode.number).padStart(2, '0')}`,
    },
    pages: [{
      id: crypto.randomUUID(),
      width: brand.width,
      height: brand.height,
      order: 1,
      layout_code: layout.code,
      brand_template_version_id: brandVersion.brand_template_version_id,
      panels: layout.panels.map((panel) => ({
        id: crypto.randomUUID(),
        rect: { x: panel.x, y: panel.y, width: panel.width, height: panel.height },
        elements: [],
      })),
    }],
  });
}

function makeBlankScript(title: string): ScriptV1 {
  return ScriptV1Schema.parse({
    schema_version: '1.0',
    title: title || '未命名故事',
    summary: '',
    theme_tags: [],
    scenes: [{
      scene_id: crypto.randomUUID(),
      name: '场景 1',
      location: '',
      time: '',
      action: '',
      character_version_ids: [],
      dialogues: [],
      panels: [],
    }],
  });
}

function flattenVersions(templates: BrandTemplateReadV1[]): BrandTemplateVersionReadV1[] {
  return templates.flatMap((template) => template.versions);
}

function elementAssetIds(document: CanvasDocumentV1 | null, brand: BrandTemplateV1 | null): string[] {
  const documentIds = document?.pages.flatMap((page) => page.panels.flatMap((panel) =>
    panel.elements.flatMap((element) =>
      element.type === 'image' || element.type === 'sticker' ? [element.asset_version_id] : [],
    ),
  )) ?? [];
  const brandIds = brand?.locked_elements.flatMap((element) => element.asset_version_id ? [element.asset_version_id] : []) ?? [];
  return [...new Set([...documentIds, ...brandIds])].sort();
}

export function ComicWorkspace({ ip }: { ip: IP }) {
  const history = useRef<{ past: CanvasDocumentV1[]; future: CanvasDocumentV1[] }>({ past: [], future: [] });
  const documentEditVersion = useRef(0);
  const [series, setSeries] = useState<SeriesReadV1[]>([]);
  const [episodes, setEpisodes] = useState<EpisodeReadV1[]>([]);
  const [templates, setTemplates] = useState<BrandTemplateReadV1[]>([]);
  const [availableAssets, setAvailableAssets] = useState<AssetVersion[]>([]);
  const [selectedSeriesId, setSelectedSeriesId] = useState('');
  const [selectedEpisodeId, setSelectedEpisodeId] = useState('');
  const [document, setDocument] = useState<CanvasDocumentV1 | null>(null);
  const [scriptRevision, setScriptRevision] = useState<ScriptRevisionReadV1 | null>(null);
  const [storyboardPanels, setStoryboardPanels] = useState<StoryboardPanelV1[]>([]);
  const [selectedGenerationPanelId, setSelectedGenerationPanelId] = useState('');
  const [generationTask, setGenerationTask] = useState<GenerationTaskV1 | null>(null);
  const [candidateRefreshKey, setCandidateRefreshKey] = useState(0);
  const [brandVersion, setBrandVersion] = useState<BrandTemplateVersionReadV1 | null>(null);
  const [assetSources, setAssetSources] = useState<Record<string, string>>({});
  const [saveStatus, setSaveStatus] = useState<'saved' | 'dirty' | 'saving' | 'conflict' | 'error'>('saved');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [seriesName, setSeriesName] = useState('');
  const [episodeTitle, setEpisodeTitle] = useState('');
  const [creatingBrand, setCreatingBrand] = useState(false);
  const [savingScript, setSavingScript] = useState(false);

  const approvedVersions = useMemo(
    () => flattenVersions(templates).filter((version) => version.status === 'approved'),
    [templates],
  );
  const selectedEpisode = episodes.find((episode) => episode.id === selectedEpisodeId) ?? null;
  const blankScript = useMemo(() => makeBlankScript(selectedEpisode?.title ?? ''), [selectedEpisode?.id, selectedEpisode?.title]);
  const assetVersionIds = useMemo(() => elementAssetIds(document, brandVersion?.template ?? null), [document, brandVersion]);
  const assetVersionKey = assetVersionIds.join('|');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setSeries([]);
    setEpisodes([]);
    setTemplates([]);
    setAvailableAssets([]);
    setSelectedSeriesId('');
    setSelectedEpisodeId('');
    setDocument(null);
    setScriptRevision(null);
    setStoryboardPanels([]);
    setSelectedGenerationPanelId('');
    setGenerationTask(null);
    setBrandVersion(null);
    history.current = { past: [], future: [] };
    Promise.all([api.getSeries(ip.id), api.getBrandTemplates(ip.id), api.getAssets(ip.id)])
      .then(([nextSeries, nextTemplates, nextAssets]) => {
        if (!active) return;
        setSeries(nextSeries);
        setTemplates(nextTemplates);
        setAvailableAssets(nextAssets);
        setSelectedSeriesId(nextSeries[0]?.id ?? '');
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : '无法读取漫画工作区');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [ip.id]);

  useEffect(() => {
    let active = true;
    setEpisodes([]);
    setSelectedEpisodeId('');
    setDocument(null);
    setScriptRevision(null);
    setStoryboardPanels([]);
    setSelectedGenerationPanelId('');
    setGenerationTask(null);
    setBrandVersion(null);
    if (!selectedSeriesId) return () => { active = false; };
    api.getEpisodes(selectedSeriesId)
      .then((nextEpisodes) => {
        if (!active) return;
        setEpisodes(nextEpisodes);
        setSelectedEpisodeId(nextEpisodes[0]?.id ?? '');
      })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : '无法读取单集'); });
    return () => { active = false; };
  }, [selectedSeriesId]);

  useEffect(() => {
    let active = true;
    setDocument(null);
    setBrandVersion(null);
    setSaveStatus('saved');
    setScriptRevision(null);
    setStoryboardPanels([]);
    setSelectedGenerationPanelId('');
    setGenerationTask(null);
    history.current = { past: [], future: [] };
    if (!selectedEpisode) return () => { active = false; };
    Promise.all([
      api.getEpisodeDocument(selectedEpisode.id),
      api.getEpisodeScripts(selectedEpisode.id),
    ])
      .then(async ([saved, scripts]) => {
        if (!active) return;
        setScriptRevision([...scripts].sort((left, right) => left.revision_no - right.revision_no).at(-1) ?? null);
        if (saved.document) {
          const version = flattenVersions(templates).find((item) =>
            item.brand_template_version_id === saved.document?.brand_template_version_id,
          ) ?? await api.getBrandTemplateVersion(saved.document.brand_template_version_id);
          if (!active) return;
          setBrandVersion(version);
          setDocument(CanvasDocumentV1Schema.parse({ ...saved.document, revision: saved.revision }));
          history.current = { past: [], future: [] };
        } else {
          const currentBrand = approvedVersions[0];
          if (!currentBrand) return;
          setBrandVersion(currentBrand);
          setDocument(makeBlankDocument(selectedEpisode, currentBrand, ip.default_style_version_id));
          history.current = { past: [], future: [] };
          setSaveStatus('dirty');
        }
      })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : '无法打开单集工作区'); });
    return () => { active = false; };
  }, [selectedEpisode, templates, approvedVersions, ip.default_style_version_id]);

  useEffect(() => {
    let active = true;
    const objectUrls: string[] = [];
    if (!assetVersionKey) {
      setAssetSources({});
      return () => { active = false; };
    }
    const byVersion = new Map(availableAssets.map((asset) => [asset.asset_version_id, asset]));
    Promise.all(assetVersionIds.map(async (versionId) => {
      const asset = byVersion.get(versionId);
      if (!asset) throw new Error(`找不到画布引用素材 ${versionId}`);
      const objectUrl = await api.getAssetPreview(ip.id, asset.asset_id, versionId);
      objectUrls.push(objectUrl);
      return [versionId, objectUrl] as const;
    }))
      .then((entries) => { if (active) setAssetSources(Object.fromEntries(entries)); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : '无法加载画布素材'); });
    return () => {
      active = false;
      objectUrls.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
    };
  }, [ip.id, assetVersionKey, availableAssets]);

  async function createSeries(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const created = await api.createSeries(ip.id, seriesName);
      setSeries((current) => [...current, created]);
      setSeriesName('');
      setSelectedSeriesId(created.id);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法创建系列');
    }
  }

  async function createEpisode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSeriesId) return;
    try {
      const number = Math.max(0, ...episodes.map((episode) => episode.number)) + 1;
      const created = await api.createEpisode(selectedSeriesId, number, episodeTitle);
      setEpisodes((current) => [...current, created]);
      setEpisodeTitle('');
      setSelectedEpisodeId(created.id);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法创建单集');
    }
  }

  async function createStarterBrand() {
    setCreatingBrand(true);
    setError('');
    try {
      const candidate = await api.createBrandTemplate(ip.id, 'IP Studio 默认品牌外壳', starterBrand());
      await api.approveBrandTemplateVersion(candidate.brand_template_version_id);
      setTemplates(await api.getBrandTemplates(ip.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法创建品牌模板');
    } finally {
      setCreatingBrand(false);
    }
  }

  async function saveDocument() {
    if (!document || !selectedEpisode || saving || saveStatus === 'saved') return;
    const editVersionAtSaveStart = documentEditVersion.current;
    setSaving(true);
    setSaveStatus('saving');
    setError('');
    try {
      const saved = await api.saveEpisodeDocument(selectedEpisode.id, document.revision, document);
      setDocument((current) => current ? { ...current, revision: saved.revision } : current);
      setSaveStatus(documentEditVersion.current === editVersionAtSaveStart ? 'saved' : 'dirty');
    } catch (cause) {
      setSaveStatus(cause instanceof Error && 'status' in cause && cause.status === 409 ? 'conflict' : 'error');
      setError(cause instanceof Error ? cause.message : '画布保存失败');
    } finally {
      setSaving(false);
    }
  }

  async function reloadCurrentDocument() {
    if (!selectedEpisode) return;
    try {
      const latest = await api.getEpisodeDocument(selectedEpisode.id);
      if (!latest.document) return;
      const version = await api.getBrandTemplateVersion(latest.document.brand_template_version_id);
      setBrandVersion(version);
      setDocument(CanvasDocumentV1Schema.parse({ ...latest.document, revision: latest.revision }));
      history.current = { past: [], future: [] };
      setSaveStatus('saved');
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法重新加载画布');
    }
  }

  async function saveScript(payload: ScriptSavePayload) {
    if (!selectedEpisode) return;
    setSavingScript(true);
    setError('');
    try {
      const saved = await api.saveEpisodeScript(
        selectedEpisode.id,
        payload.base_revision,
        payload.script,
        payload.source_markdown,
      );
      setScriptRevision(saved);
      setStoryboardPanels([]);
      setSelectedGenerationPanelId('');
      setGenerationTask(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法保存剧本修订');
      throw cause;
    } finally {
      setSavingScript(false);
    }
  }

  async function materializeStoryboard(
    baseDocumentRevision: number,
    confirmDialogueSync: boolean,
  ): Promise<ScriptMaterializationResultV1> {
    if (!selectedEpisode || !scriptRevision) throw new Error('请先保存剧本修订。');
    if (saveStatus !== 'saved') throw new Error('请先保存画布，再生成或同步分镜。');
    const result = await api.materializeScriptPanels(
      selectedEpisode.id,
      scriptRevision.revision_no,
      baseDocumentRevision,
      confirmDialogueSync,
    );
    if (result.document_revision !== document?.revision) {
      const latest = await api.getEpisodeDocument(selectedEpisode.id);
      if (latest.document) {
        setDocument(CanvasDocumentV1Schema.parse({ ...latest.document, revision: latest.revision }));
        setSaveStatus('saved');
      }
    }
    setStoryboardPanels(result.panels);
    setSelectedGenerationPanelId((current) =>
      result.panels.some((panel) => panel.panel_id === current) ? current : result.panels[0]?.panel_id ?? '',
    );
    setGenerationTask(null);
    return result;
  }

  async function createGenerationTask() {
    if (!selectedEpisode || !scriptRevision || !selectedGenerationPanelId) return;
    setError('');
    try {
      const task = await api.createGenerationTask(selectedEpisode.id, {
        script_revision_no: scriptRevision.revision_no,
        panel_id: selectedGenerationPanelId,
        mode: 'chatgpt_web',
      });
      setGenerationTask(task);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法准备人工生图任务');
    }
  }

  async function handleCodexPatchApplied() {
    if (!selectedEpisode) return;
    try {
      const latest = await api.getEpisodeDocument(selectedEpisode.id);
      if (!latest.document) return;
      setDocument(CanvasDocumentV1Schema.parse({ ...latest.document, revision: latest.revision }));
      setSaveStatus('saved');
      history.current = { past: [], future: [] };
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '已批准 Patch，但无法重新读取画布');
    }
  }

  function dispatchCanvasCommand(command: CanvasCommand) {
    if (!document) return;
    const next = applyCanvasCommand(document, command);
    documentEditVersion.current += 1;
    history.current = {
      past: [...history.current.past, document].slice(-50),
      future: [],
    };
    setDocument(next);
    setSaveStatus('dirty');
  }

  function undoCanvasCommand() {
    const previous = history.current.past.at(-1);
    if (!document || !previous) return;
    history.current = {
      past: history.current.past.slice(0, -1),
      future: [document, ...history.current.future].slice(0, 50),
    };
    documentEditVersion.current += 1;
    setDocument({ ...previous, revision: document.revision });
    setSaveStatus('dirty');
  }

  function redoCanvasCommand() {
    const [next, ...future] = history.current.future;
    if (!document || !next) return;
    history.current = {
      past: [...history.current.past, document].slice(-50),
      future,
    };
    documentEditVersion.current += 1;
    setDocument({ ...next, revision: document.revision });
    setSaveStatus('dirty');
  }

  if (loading) return <section className="comic-workspace loading-workspace" role="status">正在读取系列、模板和素材…</section>;

  return (
    <section className="comic-workspace" aria-label="漫画工作台">
      <div className="production-section-heading comic-workspace-heading">
        <div><p className="eyebrow">STORY · EPISODES · CANVAS</p><h2>漫画工作台</h2></div>
        <span>{ip.name} · {series.length} 个系列</span>
      </div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <div className="comic-workspace-selectors">
        <label>
          选择系列
          <select aria-label="选择系列" value={selectedSeriesId} disabled={saveStatus !== 'saved'} onChange={(event) => setSelectedSeriesId(event.currentTarget.value)}>
            <option value="">请选择系列</option>
            {series.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label>
          选择单集
          <select aria-label="选择单集" value={selectedEpisodeId} disabled={!selectedSeriesId || saveStatus !== 'saved'} onChange={(event) => setSelectedEpisodeId(event.currentTarget.value)}>
            <option value="">请选择单集</option>
            {episodes.map((item) => <option key={item.id} value={item.id}>EP.{String(item.number).padStart(2, '0')} · {item.title}</option>)}
          </select>
        </label>
        {selectedSeriesId && (
          <form className="comic-create-inline" onSubmit={createEpisode}>
            <label>新单集标题<input required maxLength={200} value={episodeTitle} onChange={(event) => setEpisodeTitle(event.currentTarget.value)} placeholder="下一集标题" /></label>
            <button className="button button-secondary" type="submit" disabled={saveStatus !== 'saved'}>创建单集</button>
          </form>
        )}
      </div>

      {series.length === 0 && (
        <form className="comic-empty-card" onSubmit={createSeries}>
          <div><p className="eyebrow">NEW SERIES</p><h3>从第一个系列开始</h3><p>创建系列后即可建立单集并编辑画布。</p></div>
          <label>系列名称<input required maxLength={120} value={seriesName} onChange={(event) => setSeriesName(event.currentTarget.value)} placeholder="人间卡顿局日常" /></label>
          <button className="button button-primary" type="submit">创建系列</button>
        </form>
      )}

      {approvedVersions.length === 0 && (
        <div className="comic-empty-card">
          <div><p className="eyebrow">LOCKED BRAND SHELL</p><h3>先建立 IP 品牌外壳</h3><p>默认外壳会创建为一个批准版本，后续改版需要派生新版本。</p></div>
          <button className="button button-primary" type="button" disabled={creatingBrand} onClick={() => void createStarterBrand()}>
            {creatingBrand ? '正在创建…' : '建立并批准默认外壳'}
          </button>
        </div>
      )}

      {!selectedEpisode && series.length > 0 && approvedVersions.length > 0 && (
        <div className="comic-empty-card"><div><p className="eyebrow">EPISODE CANVAS</p><h3>创建第一集</h3><p>单集会固定引用当前批准的品牌版本。</p></div></div>
      )}

      {selectedEpisode && document && brandVersion && (
        <>
          <details className="production-workflow" open>
            <summary>剧本与生图工作流</summary>
            <div className="production-workflow-grid">
              <Suspense fallback={<section className="loading-workspace" role="status">正在加载剧本与生图工具…</section>}>
              <ScriptEditor
                revisionNo={scriptRevision?.revision_no ?? 0}
                sourceMarkdown={scriptRevision?.source_markdown ?? ''}
                script={scriptRevision?.script ?? blankScript}
                onSave={saveScript}
                saving={savingScript}
              />
              <Storyboard
                panels={storyboardPanels}
                documentRevision={document.revision}
                onMaterialize={materializeStoryboard}
              />
              <section className="generation-workflow" aria-label="单格生图工作流">
                <div className="production-section-heading">
                  <div><p className="eyebrow">CHATGPT WEB · MANUAL FALLBACK</p><h2>单格生图</h2></div>
                </div>
                <p className="generation-task-note">提示词和参考版本会冻结在任务中。请在 ChatGPT Web 手动生成图片，再导入待审核候选。</p>
                <label>
                  生图目标分镜卡
                  <select
                    aria-label="生图目标分镜卡"
                    value={selectedGenerationPanelId}
                    disabled={storyboardPanels.length === 0}
                    onChange={(event) => {
                      setSelectedGenerationPanelId(event.currentTarget.value);
                      setGenerationTask(null);
                    }}
                  >
                    <option value="">先从已保存剧本生成分镜卡</option>
                    {storyboardPanels.map((panel) => (
                      <option key={panel.panel_id} value={panel.panel_id}>
                        P{String(panel.panel_order).padStart(2, '0')} · {panel.scene_name} · {panel.action}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="button button-primary"
                  type="button"
                  disabled={!scriptRevision || !selectedGenerationPanelId || saveStatus !== 'saved'}
                  onClick={() => void createGenerationTask()}
                >
                  准备 ChatGPT Web 生图任务
                </button>
                {generationTask && (
                  <>
                    <GenerationTaskCard
                      task={generationTask}
                      onStartManualGeneration={async () => {
                        const updated = await api.startManualGeneration(generationTask.task_id);
                        setGenerationTask(updated);
                        return updated;
                      }}
                      onDownloadReferenceBundle={async () => {
                        const blob = await api.getGenerationReferenceBundle(generationTask.task_id);
                        const url = URL.createObjectURL(blob);
                        const anchor = window.document.createElement('a');
                        anchor.href = url;
                        anchor.download = `ip-studio-${generationTask.task_id}-references.zip`;
                        anchor.click();
                        URL.revokeObjectURL(url);
                      }}
                      onTaskStatusChange={(status) => setGenerationTask((current) => current ? { ...current, status } : current)}
                    />
                    <ImportAssetDropzone
                      ipId={ip.id}
                      task={generationTask}
                      activePanelId={selectedGenerationPanelId}
                      onImported={() => {
                        setGenerationTask((current) => current ? { ...current, status: 'asset_imported' } : current);
                        setCandidateRefreshKey((current) => current + 1);
                      }}
                    />
                  </>
                )}
              </section>
              <CandidateReview
                ipId={ip.id}
                refreshKey={candidateRefreshKey}
                onReviewed={() => {
                  setCandidateRefreshKey((current) => current + 1);
                  void api.getAssets(ip.id).then(setAvailableAssets).catch(() => undefined);
                }}
              />
              <CodexAssistant
                episodeId={selectedEpisode.id}
                currentRevision={document.revision}
                currentDocument={document}
                onApplied={() => { void handleCodexPatchApplied(); }}
                onManualEdit={() => window.document.querySelector('.comic-editor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              />
              </Suspense>
            </div>
          </details>
          <div className="comic-save-bar">
            <span className={`save-indicator save-${saveStatus}`} role="status">{{ saved: '已保存', dirty: '有未保存更改', saving: '正在保存…', conflict: '保存冲突', error: '保存失败' }[saveStatus]}</span>
            {saveStatus === 'conflict' && <button className="button button-secondary" type="button" onClick={() => void reloadCurrentDocument()}>重新加载服务器版本</button>}
            <button className="button button-primary" type="button" disabled={saving || saveStatus === 'saved'} onClick={() => void saveDocument()}>
              {saving ? '正在保存…' : '保存画布'}
            </button>
          </div>
          <ComicEditor
            document={document}
            brand={brandVersion.template}
            onChange={(next) => {
              documentEditVersion.current += 1;
              setDocument(next);
              setSaveStatus('dirty');
            }}
            assetSources={assetSources}
            availableAssets={availableAssets}
            dispatchCommand={dispatchCanvasCommand}
            canUndo={history.current.past.length > 0}
            canRedo={history.current.future.length > 0}
            onUndo={undoCanvasCommand}
            onRedo={redoCanvasCommand}
            saveStatus={saveStatus}
          />
        </>
      )}
      {selectedEpisode && !document && approvedVersions.length > 0 && (
        <section className="loading-workspace" role="status">正在打开 {selectedEpisode.title}…</section>
      )}
    </section>
  );
}
