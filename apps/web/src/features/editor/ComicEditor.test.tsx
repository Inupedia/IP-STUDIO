import type { MouseEventHandler, ReactNode } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import canvasFixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import { BrandTemplateV1Schema } from '@ip-studio/contracts/brand';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import { ComicEditor } from './ComicEditor';

const konvaTestHarness = vi.hoisted(() => ({
  handlers: new Map<string, { onDragStart?: () => void; onDragEnd?: (event: unknown) => void }>(),
}));

vi.mock('react-konva', async () => {
  const React = await import('react');
  const node = ({ children, ...props }: { children?: ReactNode; [key: string]: unknown }) => {
    const { id, x, y, draggable, listening } = props;
    const elementId = typeof id === 'string' ? id : undefined;
    const handlers = {
      onDragStart: props.onDragStart as (() => void) | undefined,
      onDragEnd: props.onDragEnd as ((event: unknown) => void) | undefined,
    };
    const ref = elementId && (handlers.onDragStart || handlers.onDragEnd)
      ? (element: HTMLDivElement | null) => {
        if (element) konvaTestHarness.handlers.set(elementId, handlers);
        else konvaTestHarness.handlers.delete(elementId);
      }
      : undefined;
    return React.createElement(
      'div',
      {
        ref,
        'data-testid': elementId,
        'data-x': x,
        'data-y': y,
        'data-draggable': String(draggable),
        'data-listening': String(listening),
        onDoubleClick: props.onDblClick as MouseEventHandler<HTMLDivElement> | undefined,
      },
      children ?? (typeof props.text === 'string' ? props.text : undefined),
    );
  };
  return {
    Stage: node,
    Layer: node,
    Group: node,
    Rect: node,
    Text: node,
    Image: node,
    Ellipse: node,
    Line: node,
    Arrow: node,
    Transformer: node,
  };
});

const brand = BrandTemplateV1Schema.parse({
  schema_version: '1.0',
  width: 1080,
  height: 1440,
  locked_elements: [
    { id: 'fixed-logo', kind: 'logo', locked: true, x: 44, y: 40, width: 100, height: 48, fill: '#243a2d' },
    { id: 'fixed-footer', kind: 'footer', locked: true, x: 48, y: 1380, width: 984, height: 24, fill: '#eeeeee' },
  ],
  dynamic_slots: {
    title: { x: 160, y: 40, width: 760, height: 100, font_size: 48, align: 'center' },
    episode_number: { x: 900, y: 48, width: 120, height: 52, font_size: 26, align: 'right' },
  },
});

const document = CanvasDocumentV1Schema.parse(canvasFixture);

describe('ComicEditor', () => {
  afterEach(() => {
    cleanup();
    konvaTestHarness.handlers.clear();
  });

  it('keeps the logo and footer fixed while allowing title text edits', () => {
    const onChange = vi.fn();
    render(<ComicEditor document={document} brand={brand} onChange={onChange} />);

    const logo = screen.getByTestId('brand-element-fixed-logo');
    const footer = screen.getByTestId('brand-element-fixed-footer');
    expect(logo.getAttribute('data-draggable')).toBe('false');
    expect(logo.getAttribute('data-listening')).toBe('false');
    expect(footer.getAttribute('data-draggable')).toBe('false');
    expect(footer.getAttribute('data-listening')).toBe('false');

    fireEvent.change(screen.getByLabelText('页面标题'), { target: { value: '不在营业中' } });
    const updated = CanvasDocumentV1Schema.parse(onChange.mock.calls.at(-1)?.[0]);
    expect(updated.dynamic_fields.title).toBe('不在营业中');
    expect(updated.brand_template_version_id).toBe(document.brand_template_version_id);
    expect(updated.pages[0].brand_template_version_id).toBe(document.brand_template_version_id);
  });

  it('renders the exact same fixed shell positions for two episode titles', () => {
    const firstView = render(<ComicEditor document={document} brand={brand} onChange={vi.fn()} />);
    const firstLogo = firstView.getByTestId('brand-element-fixed-logo');
    firstView.unmount();

    const secondDocument = CanvasDocumentV1Schema.parse({
      ...document,
      dynamic_fields: { ...document.dynamic_fields, title: '另一集不同的标题' },
    });
    render(<ComicEditor document={secondDocument} brand={brand} onChange={vi.fn()} />);
    const secondLogo = screen.getByTestId('brand-element-fixed-logo');

    expect(secondLogo.getAttribute('data-x')).toBe(firstLogo.getAttribute('data-x'));
    expect(secondLogo.getAttribute('data-y')).toBe(firstLogo.getAttribute('data-y'));
    expect(within(screen.getByTestId('brand-shell-layer')).getByText('另一集不同的标题')).toBeTruthy();
  });

  it('offers PNG and editable PPTX export only after the document is saved', () => {
    render(<ComicEditor document={document} brand={brand} onChange={vi.fn()} saveStatus="dirty" />);

    expect(screen.getByRole('button', { name: '导出 PNG 图组' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: '导出可编辑 PPTX' }).hasAttribute('disabled')).toBe(true);
  });

  it('opens an inline text editor on double click and commits a native message layer', () => {
    const onChange = vi.fn();
    const chatElement = document.pages[0].panels[0].elements.find((element) => element.type === 'chat_message');
    if (!chatElement) throw new Error('Expected chat message fixture element');
    render(<ComicEditor document={document} brand={brand} onChange={onChange} />);

    fireEvent.doubleClick(screen.getByTestId(chatElement.id));
    const editor = screen.getByLabelText('画布内编辑文字');
    fireEvent.change(editor, { target: { value: '在吗？（已修改）' } });
    fireEvent.blur(editor);

    const updated = CanvasDocumentV1Schema.parse(onChange.mock.calls.at(-1)?.[0]);
    const updatedChat = updated.pages[0].panels[0].elements.find((element) => element.id === chatElement.id);
    expect(updatedChat?.type).toBe('chat_message');
    if (updatedChat?.type !== 'chat_message') throw new Error('Expected committed chat message');
    expect(updatedChat.props.text).toBe('在吗？（已修改）');
  });

  it('adds one approved image layer without changing the existing panel positions', () => {
    const onChange = vi.fn();
    const assetVersionId = '10000000-0000-4000-8000-000000000099';
    render(<ComicEditor
      document={document}
      brand={brand}
      onChange={onChange}
      availableAssets={[{
        asset_id: '10000000-0000-4000-8000-000000000098',
        asset_version_id: assetVersionId,
        workspace_id: '10000000-0000-4000-8000-000000000002',
        owner_ip_id: '10000000-0000-4000-8000-000000000003',
        type: 'scene',
        name: '背景参考',
        status: 'approved',
        version_no: 1,
        sha256: 'abc',
        mime: 'image/png',
        byte_size: 68,
        width: 800,
        height: 600,
        alpha: false,
        created_at: '2026-10-14T00:00:00Z',
      }]}
    />);

    fireEvent.click(screen.getByRole('button', { name: '＋ 添加已批准图片' }));

    const updated = CanvasDocumentV1Schema.parse(onChange.mock.calls.at(-1)?.[0]);
    const added = updated.pages[0].panels[0].elements.find((element) =>
      (element.type === 'image' || element.type === 'sticker') && element.asset_version_id === assetVersionId,
    );
    expect(added?.type).toBe('image');
    expect(updated.pages[0].panels[0].rect).toEqual(document.pages[0].panels[0].rect);
    expect(updated.pages[0].panels[0].elements.filter((element) => element.type === 'chat_message'))
      .toEqual(document.pages[0].panels[0].elements.filter((element) => element.type === 'chat_message'));
  });

  it('adds an approved image to the chosen panel and sizes it within that panel', () => {
    const onChange = vi.fn();
    const assetVersionId = '10000000-0000-4000-8000-000000000099';
    const targetDocument = CanvasDocumentV1Schema.parse({
      ...document,
      pages: document.pages.map((page, index) => {
        if (index !== 0) return page;
        const originalPanel = page.panels[0];
        const panelWidth = (originalPanel.rect.width - 24) / 2;
        return {
          ...page,
          layout_code: 'custom',
          panels: [
            { ...originalPanel, rect: { ...originalPanel.rect, width: panelWidth } },
            {
              id: '10000000-0000-4000-8000-000000000099',
              rect: { ...originalPanel.rect, x: originalPanel.rect.x + panelWidth + 24, width: panelWidth },
              elements: [],
            },
          ],
        };
      }),
    });
    const targetPanel = targetDocument.pages[0].panels[1];
    render(<ComicEditor
      document={targetDocument}
      brand={brand}
      onChange={onChange}
      availableAssets={[{
        asset_id: '10000000-0000-4000-8000-000000000098',
        asset_version_id: assetVersionId,
        workspace_id: '10000000-0000-4000-8000-000000000002',
        owner_ip_id: '10000000-0000-4000-8000-000000000003',
        type: 'scene',
        name: '背景参考',
        status: 'approved',
        version_no: 1,
        sha256: 'abc',
        mime: 'image/png',
        byte_size: 68,
        width: 800,
        height: 600,
        alpha: false,
        created_at: '2026-10-14T00:00:00Z',
      }]}
    />);

    fireEvent.change(screen.getByLabelText('插入目标画格'), { target: { value: targetPanel.id } });
    fireEvent.click(screen.getByRole('button', { name: '＋ 添加已批准图片' }));

    const updated = CanvasDocumentV1Schema.parse(onChange.mock.calls.at(-1)?.[0]);
    expect(updated.pages[0].panels[0]).toEqual(targetDocument.pages[0].panels[0]);
    const added = updated.pages[0].panels[1].elements.find((element) =>
      element.type === 'image' && element.asset_version_id === assetVersionId,
    );
    expect(added?.type).toBe('image');
    if (added?.type !== 'image') throw new Error('Expected the image in the chosen panel');
    expect(added.transform.width).toBeLessThanOrEqual(targetPanel.rect.width - 64);
    expect(added.transform.height).toBeLessThanOrEqual(targetPanel.rect.height - 64);
  });

  it('commits a multi-select canvas drag once after all selected nodes end', () => {
    const dispatchCommand = vi.fn();
    render(<ComicEditor document={document} brand={brand} onChange={vi.fn()} dispatchCommand={dispatchCommand} />);
    const panelElements = document.pages[0].panels[0].elements;
    const selected = panelElements.filter((element) => !element.locked).slice(0, 2);
    expect(selected).toHaveLength(2);
    const layerRows = screen.getAllByRole('button').filter((button) => button.classList.contains('editor-layer-row'));
    fireEvent.click(layerRows[panelElements.indexOf(selected[0])]);
    fireEvent.click(layerRows[panelElements.indexOf(selected[1])], { shiftKey: true });

    const first = konvaTestHarness.handlers.get(selected[0].id);
    const second = konvaTestHarness.handlers.get(selected[1].id);
    expect(first?.onDragStart).toBeTypeOf('function');
    expect(second?.onDragStart).toBeTypeOf('function');
    first?.onDragStart?.();
    second?.onDragStart?.();
    const dragEnd = { target: { x: () => 0, y: () => 0 } };
    second?.onDragEnd?.(dragEnd);
    first?.onDragEnd?.(dragEnd);

    expect(dispatchCommand).toHaveBeenCalledTimes(1);
    expect(dispatchCommand).toHaveBeenCalledWith(expect.objectContaining({
      type: 'set_transforms',
      transforms: expect.arrayContaining([
        expect.objectContaining({ element_id: selected[0].id }),
        expect.objectContaining({ element_id: selected[1].id }),
      ]),
    }));
  });
});
