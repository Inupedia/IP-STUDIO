import { useEffect, useRef } from 'react';
import Konva from 'konva';
import { Layer, Rect, Stage } from 'react-konva';
import type { BrandTemplateV1 } from '@ip-studio/contracts/brand';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import { BrandLayer } from '../editor/BrandLayer';
import { PanelLayer } from '../editor/PanelLayer';

export interface ExportPageStageProps {
  page: CanvasDocumentV1['pages'][number];
  brand: BrandTemplateV1;
  assetSources: Record<string, string>;
  title: string;
  episodeNumber: string;
  onReady: (stage: Konva.Stage) => void;
  onError: (error: Error) => void;
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(() => resolve());
    else window.setTimeout(resolve, 0);
  });
}

export function ExportPageStage({
  page,
  brand,
  assetSources,
  title,
  episodeNumber,
  onReady,
  onError,
}: ExportPageStageProps) {
  const stageRef = useRef<Konva.Stage | null>(null);
  const backgroundColor = brand.locked_elements.find(
    (element) => element.kind === 'background' && element.fill,
  )?.fill ?? '#fffefa';

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        if ('fonts' in document && document.fonts) await document.fonts.ready;
        await nextFrame();
        await nextFrame();
        const stage = stageRef.current;
        if (!stage) throw new Error('无法创建 PNG 导出画布');
        stage.batchDraw();
        if (active) onReady(stage);
      } catch (cause) {
        if (active) onError(cause instanceof Error ? cause : new Error('PNG 页面渲染失败'));
      }
    })();
    return () => { active = false; };
  }, [onError, onReady]);

  return (
    <Stage
      ref={stageRef}
      width={page.width}
      height={page.height}
      listening={false}
      style={{ background: backgroundColor }}
    >
      <Layer listening={false}>
        <Rect x={0} y={0} width={page.width} height={page.height} fill={backgroundColor} listening={false} />
      </Layer>
      <BrandLayer
        brand={brand}
        placement="background"
        title={title}
        episodeNumber={episodeNumber}
        assetSources={assetSources}
      />
      <PanelLayer
        page={page}
        assetSources={assetSources}
        onSelect={() => undefined}
        onEditText={() => undefined}
        onDragStart={() => undefined}
        onDragMove={() => undefined}
        onTransform={() => undefined}
      />
      <BrandLayer
        brand={brand}
        placement="foreground"
        title={title}
        episodeNumber={episodeNumber}
        assetSources={assetSources}
      />
    </Stage>
  );
}
