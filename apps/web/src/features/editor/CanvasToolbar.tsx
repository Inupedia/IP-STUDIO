interface CanvasToolbarProps {
  zoom: number;
  onZoomChange: (zoom: number) => void;
  showGrid: boolean;
  onGridChange: (show: boolean) => void;
  showSafeArea: boolean;
  onSafeAreaChange: (show: boolean) => void;
}

export function CanvasToolbar({
  zoom,
  onZoomChange,
  showGrid,
  onGridChange,
  showSafeArea,
  onSafeAreaChange,
}: CanvasToolbarProps) {
  const changeZoom = (delta: number) => onZoomChange(Math.max(0.25, Math.min(4, Number((zoom + delta).toFixed(2)))));
  return (
    <div className="canvas-toolbar" role="toolbar" aria-label="画布工具">
      <div className="canvas-zoom-controls">
        <button type="button" aria-label="缩小画布" disabled={zoom <= 0.25} onClick={() => changeZoom(-0.25)}>−</button>
        <span aria-live="polite">{Math.round(zoom * 100)}%</span>
        <button type="button" aria-label="放大画布" disabled={zoom >= 4} onClick={() => changeZoom(0.25)}>＋</button>
        <button type="button" onClick={() => onZoomChange(1)}>适应画布</button>
      </div>
      <div className="canvas-view-options">
        <label><input type="checkbox" checked={showGrid} onChange={(event) => onGridChange(event.currentTarget.checked)} />网格</label>
        <label><input type="checkbox" checked={showSafeArea} onChange={(event) => onSafeAreaChange(event.currentTarget.checked)} />安全区</label>
      </div>
    </div>
  );
}
