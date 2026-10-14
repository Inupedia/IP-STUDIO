interface CanvasToolbarProps {
  zoom: number;
  onZoomChange: (zoom: number) => void;
  showGrid: boolean;
  onGridChange: (show: boolean) => void;
  showSafeArea: boolean;
  onSafeAreaChange: (show: boolean) => void;
  canUndo?: boolean;
  canRedo?: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
  saveStatus?: 'saved' | 'dirty' | 'saving' | 'conflict' | 'error';
}

export function CanvasToolbar({
  zoom,
  onZoomChange,
  showGrid,
  onGridChange,
  showSafeArea,
  onSafeAreaChange,
  canUndo = false,
  canRedo = false,
  onUndo,
  onRedo,
  saveStatus = 'saved',
}: CanvasToolbarProps) {
  const changeZoom = (delta: number) => onZoomChange(Math.max(0.25, Math.min(4, Number((zoom + delta).toFixed(2)))));
  const saveLabels = {
    saved: '已保存',
    dirty: '有未保存更改',
    saving: '正在保存…',
    conflict: '保存冲突',
    error: '保存失败',
  };
  return (
    <div className="canvas-toolbar" role="toolbar" aria-label="画布工具">
      <div className="canvas-history-controls">
        <button type="button" aria-label="撤销" disabled={!canUndo} onClick={onUndo}>↶</button>
        <button type="button" aria-label="重做" disabled={!canRedo} onClick={onRedo}>↷</button>
        <span className={`save-indicator save-${saveStatus}`} role="status">{saveLabels[saveStatus]}</span>
      </div>
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
