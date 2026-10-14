import { describe, expect, it } from 'vitest';
import fixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import { applyCanvasCommand } from './commands';
import { createDocumentStore } from './DocumentStore';

const initialDocument = CanvasDocumentV1Schema.parse(fixture);
const chatElementId = initialDocument.pages[0].panels[0].elements[1].id;
const imageElementId = initialDocument.pages[0].panels[0].elements[0].id;
const nextAssetVersionId = '00000000-0000-4000-8000-000000000099';

function chatText(document: typeof initialDocument) {
  const element = document.pages[0].panels[0].elements[1];
  if (element.type !== 'chat_message') throw new Error('Expected chat message fixture element');
  return element.props.text;
}

function imageAssetVersionId(document: typeof initialDocument) {
  const element = document.pages[0].panels[0].elements[0];
  if (element.type !== 'image') throw new Error('Expected image fixture element');
  return element.asset_version_id;
}

describe('canvas commands and document history', () => {
  it('updates text and image independently and supports undo/redo', () => {
    const unlockedDocument = CanvasDocumentV1Schema.parse({
      ...initialDocument,
      pages: initialDocument.pages.map((page) => ({
        ...page,
        panels: page.panels.map((panel) => ({
          ...panel,
          elements: panel.elements.map((element) => element.id === imageElementId
            ? { ...element, locked: false }
            : element),
        })),
      })),
    });
    const store = createDocumentStore(unlockedDocument);
    store.getState().dispatch({ type: 'set_text', element_id: chatElementId, text: '改过的消息' });
    store.getState().dispatch({ type: 'replace_image', element_id: imageElementId, asset_version_id: nextAssetVersionId });

    let document = store.getState().document;
    expect(chatText(document)).toBe('改过的消息');
    expect(imageAssetVersionId(document)).toBe(nextAssetVersionId);

    store.getState().undo();
    document = store.getState().document;
    expect(imageAssetVersionId(document)).toBe(imageAssetVersionId(initialDocument));
    expect(chatText(document)).toBe('改过的消息');

    store.getState().undo();
    expect(chatText(store.getState().document)).toBe('在吗？');
    store.getState().redo();
    store.getState().redo();
    expect(imageAssetVersionId(store.getState().document)).toBe(nextAssetVersionId);
  });

  it('rejects edits to locked canvas elements', () => {
    expect(() => applyCanvasCommand(initialDocument, {
      type: 'set_transform',
      element_id: imageElementId,
      transform: { x: 1, y: 1, width: 10, height: 10, rotation: 0 },
    })).toThrow(/locked/i);
  });

  it('moves a selected group with one history step', () => {
    const groupDocument = CanvasDocumentV1Schema.parse({
      ...initialDocument,
      pages: initialDocument.pages.map((page) => ({
        ...page,
        panels: page.panels.map((panel) => ({
          ...panel,
          elements: panel.elements.map((element) => element.id === imageElementId
            ? { ...element, locked: false }
            : element),
        })),
      })),
    });
    const image = groupDocument.pages[0].panels[0].elements.find((element) => element.id === imageElementId)!;
    const chat = groupDocument.pages[0].panels[0].elements.find((element) => element.id === chatElementId)!;
    const store = createDocumentStore(groupDocument);
    store.getState().dispatch({
      type: 'set_transforms',
      transforms: [
        { element_id: image.id, transform: { ...image.transform, x: image.transform.x + 20, y: image.transform.y + 10 } },
        { element_id: chat.id, transform: { ...chat.transform, x: chat.transform.x + 20, y: chat.transform.y + 10 } },
      ],
    });

    const moved = store.getState().document.pages[0].panels[0].elements;
    expect(moved.find((element) => element.id === image.id)?.transform.x).toBe(image.transform.x + 20);
    expect(moved.find((element) => element.id === chat.id)?.transform.y).toBe(chat.transform.y + 10);
    store.getState().undo();
    expect(store.getState().document).toEqual(groupDocument);
  });
});
