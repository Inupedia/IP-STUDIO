import { useEffect, useMemo, useRef, useState } from 'react';
import Konva from 'konva';
import { Layer, Line, Rect, Stage, Transformer } from 'react-konva';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1, CanvasElementV1 } from '@ip-studio/contracts/canvas';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import type { LayoutCode } from '@ip-studio/contracts/layout';
import { applyLayout, getLayout } from '@ip-studio/contracts/layout';
import { BrandLayer } from './BrandLayer';
import { CanvasToolbar } from './CanvasToolbar';
import { LayoutPicker } from '../templates/LayoutPicker';
import { PanelLayer } from './PanelLayer';

type PresetLayoutCode = Exclude<LayoutCode, 'custom'>;
type ElementTransform = CanvasElementV1['transform'];

export interface ComicEditorProps {
  document: CanvasDocumentV1;
  brand: BrandTemplateV1;
  onChange: (document: CanvasDocumentV1) => void;
  assetSources?: Record<string, string>;
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

export function ComicEditor({ document, brand, onChange, assetSources = {} }: ComicEditorProps) {
  const [currentPageId, setCurrentPageId] = useState(document.pages[0]?.id ?? '');
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0.7);
  const [showGrid, setShowGrid] = useState(false);
  const [showSafeArea, setShowSafeArea] = useState(false);
  const [editorError, setEditorError] = useState('');
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const page = document.pages.find((candidate) => candidate.id === currentPageId) ?? document.pages[0];
  const selectedElement = findElement(page, selectedElementId);
  const backgroundElements = brand.locked_elements.filter((element) => element.kind === 'background');

  useEffect(() => {
    const stage = stageRef.current;
    const transformer = transformerRef.current;
    if (!stage || !transformer) return;
    const selected = selectedElement && !selectedElement.locked
      ? stage.findOne(`#${selectedElement.id}`)
      : undefined;
    transformer.nodes(selected ? [selected] : []);
    transformer.getLayer()?.batchDraw();
  }, [selectedElement, page]);

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
    updateDocument({
      ...document,
      dynamic_fields: { ...document.dynamic_fields, [field]: value },
    });
  }

  function updateElementTransform(elementId: string, transform: ElementTransform) {
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

  function changeLayout(code: PresetLayoutCode) {
    try {
      const layout = getLayout(code, page.width, page.height);
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
          elements: existing?.elements ?? [],
        };
      });
      updateDocument({
        ...document,
        pages: document.pages.map((candidate) => candidate.id === page.id
          ? { ...candidate, layout_code: code, panels: nextPanels }
          : candidate),
      });
      setSelectedElementId(null);
      setEditorError('');
    } catch (cause) {
      setEditorError(cause instanceof Error ? cause.message : '无法切换画格布局');
    }
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
                    onSelect={setSelectedElementId}
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
          <div className="editor-layer-list">
            {page.panels.flatMap((panel, panelIndex) => panel.elements.map((element) => (
              <button
                key={element.id}
                type="button"
                className={`editor-layer-row ${selectedElementId === element.id ? 'is-selected' : ''}`}
                aria-pressed={selectedElementId === element.id}
                onClick={() => setSelectedElementId(element.id)}
              >
                <span className="layer-type-mark">{element.type.slice(0, 1).toUpperCase()}</span>
                <span>{element.type === 'chat_message' ? element.props.text : element.type}</span>
                <small>格 {panelIndex + 1}</small>
              </button>
            )))}
            {page.panels.every((panel) => panel.elements.length === 0) && <p className="editor-empty-layers">当前页面还没有内容图层。</p>}
          </div>
          {selectedElement && (
            <div className="selected-element-card" aria-label="选中图层详情">
              <span>选中图层</span>
              <strong>{selectedElement.type}</strong>
              <small>{selectedElement.locked ? '此图层已锁定' : '可在画布中拖动与调整大小'}</small>
              {selectedElement.type === 'chat_message' && selectedElement.props.direction_override && (
                <small className="direction-override-note">方向被手动覆盖为{selectedElement.props.direction_override === 'right' ? '右侧' : '左侧'}</small>
              )}
            </div>
          )}
          <p className="editor-lock-note">品牌背景、Logo、标题栏和页脚只能在品牌模板中派生新版本后更改。</p>
        </aside>
      </div>
    </section>
  );
}
