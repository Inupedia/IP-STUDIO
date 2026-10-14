import { useEffect, useMemo, useRef, useState } from 'react';
import Konva from 'konva';
import { Layer, Line, Rect, Stage, Transformer } from 'react-konva';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1, CanvasElementV1 } from '@ip-studio/contracts/canvas';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import type { AssetVersion } from '@ip-studio/contracts/domain';
import type { LayoutCode } from '@ip-studio/contracts/layout';
import { applyLayout, getLayout } from '@ip-studio/contracts/layout';
import { BrandLayer } from './BrandLayer';
import { CanvasToolbar } from './CanvasToolbar';
import { LayoutPicker } from '../templates/LayoutPicker';
import { PanelLayer } from './PanelLayer';
import { applyCanvasCommand, type CanvasCommand } from './commands';
import { ReplacePanelImage } from './ReplacePanelImage';
import { ExportPanel } from '../export/ExportPanel';
import { canvasElementMayOverflowText } from './textOverflow';

type PresetLayoutCode = Exclude<LayoutCode, 'custom'>;
type ElementTransform = CanvasElementV1['transform'];

export interface ComicEditorProps {
  document: CanvasDocumentV1;
  brand: BrandTemplateV1;
  onChange: (document: CanvasDocumentV1) => void;
  assetSources?: Record<string, string>;
  availableAssets?: AssetVersion[];
  dispatchCommand?: (command: CanvasCommand) => void;
  canUndo?: boolean;
  canRedo?: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
  saveStatus?: 'saved' | 'dirty' | 'saving' | 'conflict' | 'error';
}

function presetFromPage(page: CanvasDocumentV1['pages'][number]): PresetLayoutCode {
  if (page.layout_code === 'four' || page.layout_code === 'six' || page.layout_code === 'eight') {
    return page.layout_code;
  }
  if (page.panels.length === 6) return 'six';
  if (page.panels.length === 8) return 'eight';
  return 'four';
}

function findElement(page: CanvasDocumentV1['pages'][number], elementId: string | null) {
  if (!elementId) return null;
  for (const panel of page.panels) {
    const element = panel.elements.find((candidate) => candidate.id === elementId);
    if (element) return element;
  }
  return null;
}

function withElementText(element: CanvasElementV1, text: string): CanvasElementV1 {
  switch (element.type) {
    case 'text':
      return { ...element, props: { ...element.props, text } };
    case 'chat_message':
      return { ...element, props: { ...element.props, text } };
    case 'speech_bubble':
      return { ...element, props: { ...element.props, text } };
    case 'thought_bubble':
      return { ...element, props: { ...element.props, text } };
    default:
      return element;
  }
}

function getEditableText(element: CanvasElementV1): string | null {
  switch (element.type) {
    case 'text':
    case 'chat_message':
    case 'speech_bubble':
    case 'thought_bubble':
      return element.props.text;
    default:
      return null;
  }
}

export function ComicEditor({
  document,
  brand,
  onChange,
  assetSources = {},
  availableAssets = [],
  dispatchCommand,
  canUndo = false,
  canRedo = false,
  onUndo,
  onRedo,
  saveStatus = 'saved',
}: ComicEditorProps) {
  const [currentPageId, setCurrentPageId] = useState(document.pages[0]?.id ?? '');
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [selectedElementIds, setSelectedElementIds] = useState<string[]>([]);
  const [groupMoveX, setGroupMoveX] = useState('0');
  const [groupMoveY, setGroupMoveY] = useState('0');
  const [zoom, setZoom] = useState(0.7);
  const [showGrid, setShowGrid] = useState(false);
  const [showSafeArea, setShowSafeArea] = useState(false);
  const [editorError, setEditorError] = useState('');
  const [inlineEdit, setInlineEdit] = useState<{ elementId: string; value: string } | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const groupDragOrigin = useRef<Map<string, ElementTransform> | null>(null);
  const page = document.pages.find((candidate) => candidate.id === currentPageId) ?? document.pages[0];
  const selectedElement = findElement(page, selectedElementId);
  const selectedPanel = page.panels.find((panel) =>
    panel.elements.some((element) => element.id === selectedElementId),
  );
  const inlineEditElement = inlineEdit ? findElement(page, inlineEdit.elementId) : null;
  const inlineEditPanel = inlineEdit
    ? page.panels.find((panel) => panel.elements.some((element) => element.id === inlineEdit.elementId)) ?? null
    : null;
  const overflowingTextCount = page.panels
    .flatMap((panel) => panel.elements)
    .filter(canvasElementMayOverflowText).length;
  const backgroundElements = brand.locked_elements.filter((element) => element.kind === 'background');

  useEffect(() => {
    const stage = stageRef.current;
    const transformer = transformerRef.current;
    if (!stage || !transformer) return;
    const selectedNodes = selectedElementIds.flatMap((elementId) => {
      const element = findElement(page, elementId);
      const node = element && !element.locked ? stage.findOne(`#${elementId}`) : undefined;
      return node ? [node] : [];
    });
    transformer.nodes(selectedNodes);
    transformer.getLayer()?.batchDraw();
  }, [selectedElement, selectedElementIds, page]);

  const gridLines = useMemo(() => {
    const lines: { points: number[]; key: string }[] = [];
    for (let x = 40; x < page.width; x += 40) {
      lines.push({ key: `x-${x}`, points: [x, 0, x, page.height] });
    }
    for (let y = 40; y < page.height; y += 40) {
      lines.push({ key: `y-${y}`, points: [0, y, page.width, y] });
    }
    return lines;
  }, [page.height, page.width]);

  function updateDocument(next: CanvasDocumentV1) {
    onChange(CanvasDocumentV1Schema.parse(next));
  }

  function updateDynamicField(field: 'title' | 'episode_number', value: string) {
    if (dispatchCommand) {
      dispatchCommand({ type: 'set_dynamic_field', field, value });
      return;
    }
    updateDocument({
      ...document,
      dynamic_fields: { ...document.dynamic_fields, [field]: value },
    });
  }

  function updateElementTransform(elementId: string, transform: ElementTransform) {
    const groupStart = groupDragOrigin.current;
    if (groupStart?.has(elementId)) {
      const stage = stageRef.current;
      const transforms = [...groupStart].map(([id, original]) => {
        const node = stage?.findOne(`#${id}`);
        return {
          element_id: id,
          transform: { ...original, x: node?.x() ?? original.x, y: node?.y() ?? original.y },
        };
      });
      groupDragOrigin.current = null;
      updateElementTransforms(transforms);
      return;
    }
    if (dispatchCommand) {
      dispatchCommand({ type: 'set_transform', element_id: elementId, transform });
      return;
    }
    const next = {
      ...document,
      pages: document.pages.map((currentPage) => ({
        ...currentPage,
        panels: currentPage.panels.map((panel) => ({
          ...panel,
          elements: panel.elements.map((element) => element.id === elementId
            ? { ...element, transform }
            : element),
        })),
      })),
    };
    updateDocument(next);
  }

  function updateElementTransforms(transforms: Array<{ element_id: string; transform: ElementTransform }>) {
    if (dispatchCommand) {
      dispatchCommand({ type: 'set_transforms', transforms });
      return;
    }
    updateDocument(applyCanvasCommand(document, { type: 'set_transforms', transforms }));
  }

  function beginGroupDrag(elementId: string) {
    if (selectedElementIds.length < 2 || !selectedElementIds.includes(elementId)) {
      groupDragOrigin.current = null;
      return;
    }
    groupDragOrigin.current = new Map(selectedElementIds.flatMap((id) => {
      const element = findElement(page, id);
      return element && !element.locked ? [[id, element.transform] as const] : [];
    }));
  }

  function moveGroupDuringDrag(elementId: string, position: { x: number; y: number }) {
    const origins = groupDragOrigin.current;
    const stage = stageRef.current;
    const origin = origins?.get(elementId);
    if (!origins || !stage || !origin) return;
    const dx = position.x - origin.x;
    const dy = position.y - origin.y;
    for (const [id, startingTransform] of origins) {
      if (id === elementId) continue;
      stage.findOne(`#${id}`)?.position({
        x: startingTransform.x + dx,
        y: startingTransform.y + dy,
      });
    }
    stage.batchDraw();
  }

  function applyGroupMove() {
    const dx = Number(groupMoveX);
    const dy = Number(groupMoveY);
    if (!Number.isFinite(dx) || !Number.isFinite(dy) || (dx === 0 && dy === 0)) return;
    const elements = selectedElementIds.map((elementId) => findElement(page, elementId));
    if (elements.some((element) => !element || element.locked)) {
      setEditorError('所选图层中包含锁定或已移除的元素。');
      return;
    }
    const transforms = selectedElementIds.map((elementId, index) => {
      const element = elements[index]!;
      return {
        element_id: elementId,
        transform: { ...element.transform, x: element.transform.x + dx, y: element.transform.y + dy },
      };
    });
    updateElementTransforms(transforms);
    setEditorError('');
  }

  function selectElement(elementId: string, additive = false) {
    const element = findElement(page, elementId);
    if (element?.locked && additive) return;
    if (additive && selectedElementIds.length > 0) {
      const originalPanelId = page.panels.find((panel) => panel.elements.some((item) => item.id === selectedElementIds[0]))?.id;
      const targetPanelId = page.panels.find((panel) => panel.elements.some((item) => item.id === elementId))?.id;
      if (originalPanelId !== targetPanelId) {
        setEditorError('请在同一画格内多选并移动图层。');
        return;
      }
    }
    const nextIds = additive
      ? selectedElementIds.includes(elementId)
        ? selectedElementIds.filter((selectedId) => selectedId !== elementId)
        : [...selectedElementIds, elementId]
      : [elementId];
    setSelectedElementIds(nextIds);
    setSelectedElementId(nextIds.at(-1) ?? null);
  }

  function changeLayout(code: PresetLayoutCode) {
    try {
      const layout = getLayout(code, page.width, page.height);
      if (dispatchCommand) {
        dispatchCommand({ type: 'set_layout', page_id: page.id, layout });
        setSelectedElementId(null);
        setSelectedElementIds([]);
        setEditorError('');
        return;
      }
      const flatPage = {
        brand_template_version_id: page.brand_template_version_id,
        panels: page.panels.map((panel) => ({
          panel_id: panel.id,
          ...panel.rect,
          elements: panel.elements,
        })),
      };
      const updated = applyLayout(flatPage, layout);
      const nextPanels = updated.panels.map((panel, index) => {
        const existing = page.panels.find((candidate) => candidate.id === panel.panel_id) ?? page.panels[index];
        return {
          id: existing?.id ?? crypto.randomUUID(),
          rect: { x: panel.x, y: panel.y, width: panel.width, height: panel.height },
          elements: (existing?.elements as CanvasElementV1[] | undefined) ?? [],
        };
      });
      updateDocument({
        ...document,
        pages: document.pages.map((candidate) => candidate.id === page.id
          ? { ...candidate, layout_code: code, panels: nextPanels }
          : candidate),
      });
      setSelectedElementId(null);
      setSelectedElementIds([]);
      setEditorError('');
    } catch (cause) {
      setEditorError(cause instanceof Error ? cause.message : '无法切换画格布局');
    }
  }

  function updateElementText(elementId: string, text: string) {
    if (dispatchCommand) {
      dispatchCommand({ type: 'set_text', element_id: elementId, text });
      return;
    }
    updateDocument({
      ...document,
      pages: document.pages.map((currentPage) => ({
        ...currentPage,
        panels: currentPage.panels.map((panel) => ({
          ...panel,
          elements: panel.elements.map((element) => {
            if (element.id !== elementId) return element;
            return withElementText(element, text);
          }),
        })),
      })),
    });
  }

  function startInlineEdit(elementId: string) {
    const element = findElement(page, elementId);
    if (!element || element.locked) return;
    const value = getEditableText(element);
    if (value === null) return;
    setSelectedElementId(elementId);
    setSelectedElementIds([elementId]);
    setInlineEdit({ elementId, value });
  }

  function commitInlineEdit() {
    if (!inlineEdit) return;
    const current = findElement(page, inlineEdit.elementId);
    if (current && getEditableText(current) !== inlineEdit.value) {
      updateElementText(inlineEdit.elementId, inlineEdit.value);
    }
    setInlineEdit(null);
  }

  function updateImageCrop(elementId: string, crop: { x: number; y: number; width: number; height: number }) {
    if (dispatchCommand) {
      dispatchCommand({ type: 'set_crop', element_id: elementId, crop });
      return;
    }
    updateDocument({
      ...document,
      pages: document.pages.map((currentPage) => ({
        ...currentPage,
        panels: currentPage.panels.map((panel) => ({
          ...panel,
          elements: panel.elements.map((element) => element.id === elementId && element.type === 'image'
            ? { ...element, crop }
            : element),
        })),
      })),
    });
  }

  function addElement(element: CanvasElementV1) {
    if (dispatchCommand) {
      dispatchCommand({ type: 'add_element', panel_id: page.panels[0].id, element });
      setSelectedElementId(element.id);
      setSelectedElementIds([element.id]);
      return;
    }
    updateDocument({
      ...document,
      pages: document.pages.map((currentPage) => currentPage.id === page.id
        ? {
          ...currentPage,
          panels: currentPage.panels.map((panel, index) => index === 0
            ? { ...panel, elements: [...panel.elements, element] }
            : panel),
        }
        : currentPage),
    });
    setSelectedElementId(element.id);
    setSelectedElementIds([element.id]);
  }

  function addTextElement() {
    const topZ = Math.max(0, ...page.panels.flatMap((panel) => panel.elements.map((element) => element.z_index))) + 1;
    addElement({
      id: crypto.randomUUID(),
      type: 'text',
      props: { text: '在属性栏编辑文字', font_family: 'sans-serif', font_size: 32, font_weight: 400, color: '#242923', align: 'left', line_height: 1.3, letter_spacing: 0 },
      transform: { x: 40, y: 40, width: 360, height: 90, rotation: 0 },
      opacity: 1,
      z_index: topZ,
      locked: false,
    });
  }

  function addImageElement() {
    const panel = page.panels[0];
    const asset = availableAssets.find((candidate) => candidate.status === 'approved');
    if (!panel || !asset) {
      setEditorError('请先在当前 IP 素材库批准一张图片，再添加到画格。');
      return;
    }
    const maxWidth = Math.max(1, panel.rect.width - 64);
    const maxHeight = Math.max(1, panel.rect.height - 64);
    const aspectRatio = asset.width / asset.height;
    const width = Math.min(maxWidth, maxHeight * aspectRatio);
    const height = width / aspectRatio;
    const topZ = Math.max(0, ...panel.elements.map((element) => element.z_index)) + 1;
    addElement({
      id: crypto.randomUUID(),
      type: 'image',
      asset_version_id: asset.asset_version_id,
      transform: { x: 32, y: 32, width, height, rotation: 0 },
      crop: { x: 0, y: 0, width: 1, height: 1 },
      opacity: 1,
      z_index: topZ,
      locked: false,
    });
  }

  function addSpeechBubbleElement() {
    const panel = page.panels[0];
    if (!panel) return;
    const topZ = Math.max(0, ...panel.elements.map((element) => element.z_index)) + 1;
    addElement({
      id: crypto.randomUUID(),
      type: 'speech_bubble',
      props: {
        text: '在属性栏编辑气泡文字',
        shape: 'rounded_rectangle',
        fill: '#ffffff',
        stroke: '#242923',
        stroke_width: 2,
        tail_position: 'bottom',
        font_family: 'sans-serif',
        font_size: 28,
      },
      transform: { x: 40, y: 150, width: 360, height: 120, rotation: 0 },
      opacity: 1,
      z_index: topZ,
      locked: false,
    });
  }

  function deleteSelectedElement() {
    if (!selectedElement || selectedElement.locked) return;
    if (dispatchCommand) {
      dispatchCommand({ type: 'delete_element', element_id: selectedElement.id });
    } else {
      updateDocument({
        ...document,
        pages: document.pages.map((currentPage) => ({
          ...currentPage,
          panels: currentPage.panels.map((panel) => ({
            ...panel,
            elements: panel.elements.filter((element) => element.id !== selectedElement.id),
          })),
        })),
      });
    }
    setSelectedElementId(null);
    setSelectedElementIds([]);
  }

  return (
    <section className="comic-editor" aria-label="漫画画布编辑器">
      <CanvasToolbar
        zoom={zoom}
        onZoomChange={setZoom}
        showGrid={showGrid}
        onGridChange={setShowGrid}
        showSafeArea={showSafeArea}
        onSafeAreaChange={setShowSafeArea}
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={onUndo}
        onRedo={onRedo}
        saveStatus={saveStatus}
      />
      <div className="editor-workbench">
        <aside className="editor-page-rail" aria-label="页面列表">
          <div className="editor-rail-heading">
            <p className="eyebrow">EPISODE</p>
            <h3>页面</h3>
          </div>
          <div className="editor-page-list">
            {document.pages.map((item, index) => (
              <button
                key={item.id}
                type="button"
                className={`editor-page-button ${item.id === page.id ? 'is-selected' : ''}`}
                aria-pressed={item.id === page.id}
                onClick={() => {
                  setCurrentPageId(item.id);
                  setSelectedElementId(null);
                  setSelectedElementIds([]);
                  setInlineEdit(null);
                }}
              >
                <span className="editor-page-thumb" aria-hidden="true">
                  {item.panels.slice(0, 8).map((panel) => <i key={panel.id} />)}
                </span>
                <span>第 {index + 1} 页</span>
              </button>
            ))}
          </div>
        </aside>

        <main className="editor-canvas-column">
          <div className="editor-canvas-heading">
            <div>
              <p className="eyebrow">CANVAS DOCUMENT · V1</p>
              <h2>{document.dynamic_fields.episode_number} · {document.dynamic_fields.title || '未命名页面'}</h2>
            </div>
            <span className="editor-brand-lock">外壳锁定 · 品牌版本 {document.brand_template_version_id.slice(0, 8)}</span>
          </div>
          {editorError && <p className="editor-error" role="alert">{editorError}</p>}
          {overflowingTextCount > 0 && (
            <p className="editor-warning" role="alert">
              有 {overflowingTextCount} 个文字元素文字可能超出文本框；请缩短文字或调整文本框尺寸后再导出。
            </p>
          )}
          <div className="canvas-scroll-area">
            <div
              className="canvas-stage-viewport"
              style={{ width: page.width * zoom, height: page.height * zoom }}
            >
              <div
                className="canvas-stage-transform"
                style={{ width: page.width, height: page.height, transform: `scale(${zoom})` }}
              >
                <Stage
                  ref={stageRef}
                  width={page.width}
                  height={page.height}
                  style={{ background: backgroundElements.find((element) => element.fill)?.fill ?? '#fffefa' }}
                >
                  <BrandLayer
                    brand={brand}
                    placement="background"
                    title={document.dynamic_fields.title}
                    episodeNumber={document.dynamic_fields.episode_number}
                    assetSources={assetSources}
                  />
                  <PanelLayer
                    page={page}
                    assetSources={assetSources}
                    onSelect={selectElement}
                    onEditText={startInlineEdit}
                    onDragStart={beginGroupDrag}
                    onDragMove={moveGroupDuringDrag}
                    onTransform={updateElementTransform}
                  />
                  {(showGrid || showSafeArea) && (
                    <Layer listening={false} id="editor-guides-layer">
                      {showGrid && gridLines.map((line) => (
                        <Line key={line.key} points={line.points} stroke="#73806d" strokeWidth={1} opacity={0.15} listening={false} />
                      ))}
                      {showSafeArea && (
                        <Rect
                          x={48}
                          y={48}
                          width={Math.max(1, page.width - 96)}
                          height={Math.max(1, page.height - 96)}
                          stroke="#b27045"
                          strokeWidth={2}
                          dash={[10, 8]}
                          listening={false}
                        />
                      )}
                    </Layer>
                  )}
                  <BrandLayer
                    brand={brand}
                    placement="foreground"
                    title={document.dynamic_fields.title}
                    episodeNumber={document.dynamic_fields.episode_number}
                    assetSources={assetSources}
                  />
                  <Layer id="selection-layer">
                    <Transformer
                      ref={transformerRef}
                      rotateEnabled
                      keepRatio={selectedElement?.type === 'image' || selectedElement?.type === 'sticker'}
                      enabledAnchors={['top-left', 'top-right', 'bottom-left', 'bottom-right', 'middle-left', 'middle-right', 'top-center', 'bottom-center']}
                      borderStroke="#6b8065"
                      anchorStroke="#6b8065"
                      anchorFill="#fffefa"
                      anchorSize={9}
                    />
                  </Layer>
                </Stage>
                {inlineEdit && inlineEditElement && inlineEditPanel && getEditableText(inlineEditElement) !== null && (
                  <textarea
                    autoFocus
                    aria-label="画布内编辑文字"
                    className="canvas-inline-text-editor"
                    style={{
                      left: inlineEditPanel.rect.x + inlineEditElement.transform.x,
                      top: inlineEditPanel.rect.y + inlineEditElement.transform.y,
                      width: inlineEditElement.transform.width,
                      height: inlineEditElement.transform.height,
                      transform: `rotate(${inlineEditElement.transform.rotation}deg)`,
                    }}
                    value={inlineEdit.value}
                    onChange={(event) => setInlineEdit({ ...inlineEdit, value: event.currentTarget.value })}
                    onBlur={commitInlineEdit}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') setInlineEdit(null);
                      if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) event.currentTarget.blur();
                    }}
                  />
                )}
              </div>
            </div>
          </div>
          <div className="editor-status-line" aria-live="polite">
            <span>{page.width} × {page.height} px</span>
            <span>{page.panels.length} 格</span>
            <span>{page.panels.reduce((count, panel) => count + panel.elements.length, 0)} 个独立图层</span>
          </div>
        </main>

        <aside className="editor-properties" aria-label="页面和图层属性">
          <div className="editor-properties-heading">
            <p className="eyebrow">PROPERTIES</p>
            <h3>页面属性</h3>
          </div>
          <LayoutPicker value={presetFromPage(page)} onChange={changeLayout} brandVersionLabel={`v${document.brand_template_version_id.slice(0, 8)}`} />
          <div className="editor-property-fields">
            <label>
              页面标题
              <input value={document.dynamic_fields.title} maxLength={1000} onChange={(event) => updateDynamicField('title', event.currentTarget.value)} />
            </label>
            <label>
              EP 编号
              <input value={document.dynamic_fields.episode_number} maxLength={32} onChange={(event) => updateDynamicField('episode_number', event.currentTarget.value)} />
            </label>
          </div>
          <div className="editor-properties-heading layers-heading">
            <p className="eyebrow">LAYERS</p>
            <h3>当前画格图层</h3>
          </div>
          <div className="editor-insert-controls">
            <button type="button" onClick={addTextElement}>＋ 添加文字</button>
            <button type="button" disabled={!availableAssets.some((asset) => asset.status === 'approved')} onClick={addImageElement}>＋ 添加已批准图片</button>
            <button type="button" onClick={addSpeechBubbleElement}>＋ 添加对白气泡</button>
          </div>
          <div className="editor-layer-list">
            {page.panels.flatMap((panel, panelIndex) => panel.elements.map((element) => (
              <button
                key={element.id}
                type="button"
                className={`editor-layer-row ${selectedElementIds.includes(element.id) ? 'is-selected' : ''}`}
                aria-pressed={selectedElementIds.includes(element.id)}
                onClick={(event) => selectElement(element.id, event.shiftKey || event.metaKey || event.ctrlKey)}
              >
                <span className="layer-type-mark">{element.type.slice(0, 1).toUpperCase()}</span>
                <span>{element.type === 'chat_message' ? element.props.text : element.type}</span>
                <small>格 {panelIndex + 1}</small>
              </button>
            )))}
            {page.panels.every((panel) => panel.elements.length === 0) && <p className="editor-empty-layers">当前页面还没有内容图层。</p>}
          </div>
          <p className="editor-selection-hint">按 Shift、⌘ 或 Ctrl 点击图层可多选。</p>
          {selectedElementIds.length > 1 && (
            <div className="selected-group-controls" aria-label="多图层选择">
              <strong>已选择 {selectedElementIds.length} 个图层</strong>
              <label>整体水平位移（px）<input aria-label="整体水平位移" type="number" value={groupMoveX} onChange={(event) => setGroupMoveX(event.currentTarget.value)} /></label>
              <label>整体垂直位移（px）<input aria-label="整体垂直位移" type="number" value={groupMoveY} onChange={(event) => setGroupMoveY(event.currentTarget.value)} /></label>
              <button className="button button-secondary" type="button" onClick={applyGroupMove}>整体移动所选图层</button>
            </div>
          )}
          {selectedElement && (
            <div className="selected-element-card" aria-label="选中图层详情">
              <span>选中图层</span>
              <strong>{selectedElement.type}</strong>
              <small>{selectedElement.locked ? '此图层已锁定' : '可在画布中拖动与调整大小'}</small>
              {selectedElement.type === 'chat_message' && selectedElement.props.direction_override && (
                <small className="direction-override-note">方向被手动覆盖为{selectedElement.props.direction_override === 'right' ? '右侧' : '左侧'}</small>
              )}
              {!selectedElement.locked && (
                <>
                  {(selectedElement.type === 'text' || selectedElement.type === 'speech_bubble'
                    || selectedElement.type === 'thought_bubble' || selectedElement.type === 'chat_message') && (
                    <label>
                      {selectedElement.type === 'chat_message' ? '消息文字' : '文字内容'}
                      <textarea
                        aria-label="图层文字内容"
                        rows={3}
                        maxLength={10000}
                        value={selectedElement.props.text}
                        onChange={(event) => updateElementText(selectedElement.id, event.currentTarget.value)}
                      />
                    </label>
                  )}
                  {(selectedElement.type === 'image' || selectedElement.type === 'sticker') && (
                    selectedPanel && (
                      <ReplacePanelImage
                        document={document}
                        panelId={selectedPanel.id}
                        imageElementId={selectedElement.id}
                        currentAssetVersionId={selectedElement.asset_version_id}
                        availableAssets={availableAssets}
                        onReplace={(command) => {
                          if (dispatchCommand) dispatchCommand(command);
                          else updateDocument(applyCanvasCommand(document, command));
                        }}
                      />
                    )
                  )}
                  {selectedElement.type === 'image' && (
                    <div className="crop-controls">
                      <span>图片裁切</span>
                      {(['x', 'y', 'width', 'height'] as const).map((axis) => (
                        <label key={axis}>
                          {({ x: '左', y: '上', width: '宽', height: '高' })[axis]}
                          <input
                            type="range"
                            min={axis === 'x' || axis === 'y' ? 0 : 0.001}
                            max={axis === 'x' ? 1 - selectedElement.crop.width
                              : axis === 'y' ? 1 - selectedElement.crop.height
                                : axis === 'width' ? 1 - selectedElement.crop.x
                                  : 1 - selectedElement.crop.y}
                            step={0.001}
                            value={selectedElement.crop[axis]}
                            onChange={(event) => {
                              const value = Number(event.currentTarget.value);
                              const crop = { ...selectedElement.crop, [axis]: value };
                              updateImageCrop(selectedElement.id, crop);
                            }}
                          />
                        </label>
                      ))}
                    </div>
                  )}
                  <button type="button" className="editor-delete-button" onClick={deleteSelectedElement}>删除图层</button>
                </>
              )}
            </div>
          )}
          <p className="editor-lock-note">品牌背景、Logo、标题栏和页脚只能在品牌模板中派生新版本后更改。</p>
          <ExportPanel
            episodeId={document.episode_id}
            currentRevision={document.revision}
            canvasDocument={document}
            brand={brand}
            assetSources={assetSources}
            isSaved={saveStatus === 'saved'}
          />
        </aside>
      </div>
    </section>
  );
}
