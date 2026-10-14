import type { MouseEventHandler, ReactNode } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import canvasFixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import { BrandTemplateV1Schema } from '@ip-studio/contracts/brand';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import { ComicEditor } from './ComicEditor';

vi.mock('react-konva', async () => {
  const React = await import('react');
  const node = ({ children, ...props }: { children?: ReactNode; [key: string]: unknown }) => {
    const { id, x, y, draggable, listening } = props;
    return React.createElement(
      'div',
      {
        'data-testid': typeof id === 'string' ? id : undefined,
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
  afterEach(cleanup);

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
});
