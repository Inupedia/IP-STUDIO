import type { LayoutCode } from '@ip-studio/contracts/layout';

const layouts: { code: Exclude<LayoutCode, 'custom'>; label: string; rows: number }[] = [
  { code: 'four', label: '四格', rows: 2 },
  { code: 'six', label: '六格', rows: 3 },
  { code: 'eight', label: '八格', rows: 4 },
];

interface LayoutPickerProps {
  value: Exclude<LayoutCode, 'custom'>;
  onChange: (code: Exclude<LayoutCode, 'custom'>) => void;
  brandVersionLabel: string;
}

export function LayoutPicker({ value, onChange, brandVersionLabel }: LayoutPickerProps) {
  return (
    <section className="layout-picker" aria-label="画格布局">
      <div className="layout-picker-heading">
        <div>
          <p className="eyebrow">PAGE LAYOUT</p>
          <h3>选择画格布局</h3>
        </div>
        <p>品牌外壳 <strong>{brandVersionLabel}</strong></p>
      </div>
      <div className="layout-options">
        {layouts.map((layout) => (
          <button
            key={layout.code}
            type="button"
            aria-pressed={value === layout.code}
            className={`layout-option ${value === layout.code ? 'is-selected' : ''}`}
            onClick={() => onChange(layout.code)}
          >
            <span className="layout-preview" aria-hidden="true">
              {Array.from({ length: layout.rows * 2 }, (_, index) => <i key={index} />)}
            </span>
            <span>{layout.label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
