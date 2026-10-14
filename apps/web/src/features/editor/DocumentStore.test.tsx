import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import { createDocumentStore, useDocumentAutosave, type DocumentSaveResult, type SaveDocument } from './DocumentStore';

const document = CanvasDocumentV1Schema.parse(fixture);
const chatId = document.pages[0].panels[0].elements[1].id;

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('DocumentStore autosave', () => {
  it('debounces writes for 1.5 seconds and advances the saved revision', async () => {
    vi.useFakeTimers();
    const store = createDocumentStore(document);
    const save = vi.fn(async (baseRevision: number) => ({
      revision: baseRevision + 1,
      document,
    }));
    renderHook(() => useDocumentAutosave(store, save));
    act(() => store.getState().dispatch({ type: 'set_text', element_id: chatId, text: '保存这句话' }));

    await act(async () => { await vi.advanceTimersByTimeAsync(1499); });
    expect(save).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith(document.revision, expect.objectContaining({
      pages: expect.any(Array),
    }));
    expect(store.getState().revision).toBe(document.revision + 1);
    expect(store.getState().saveStatus).toBe('saved');
  });

  it('stops automatic retries on a revision conflict', async () => {
    vi.useFakeTimers();
    const store = createDocumentStore(document);
    const conflict = Object.assign(new Error('文档已被另一个标签页更新'), { status: 409 });
    const save = vi.fn(async () => { throw conflict; });
    renderHook(() => useDocumentAutosave(store, save));
    act(() => store.getState().dispatch({ type: 'set_text', element_id: chatId, text: '本地未保存的内容' }));

    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });

    expect(save).toHaveBeenCalledTimes(1);
    expect(store.getState().saveStatus).toBe('conflict');
    expect(store.getState().isDirty).toBe(true);
  });

  it('queues edits made during a save and uses the new revision for the next write', async () => {
    vi.useFakeTimers();
    const store = createDocumentStore(document);
    const resolvers: Array<(result: DocumentSaveResult) => void> = [];
    const save = vi.fn<SaveDocument>((baseRevision, snapshot) => new Promise<DocumentSaveResult>((resolve) => {
      resolvers.push((result) => resolve(result));
      expect(baseRevision).toBeGreaterThanOrEqual(document.revision);
      expect(snapshot).toBeDefined();
    }));
    renderHook(() => useDocumentAutosave(store, save));
    act(() => store.getState().dispatch({ type: 'set_text', element_id: chatId, text: '第一次修改' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(save).toHaveBeenCalledTimes(1);

    act(() => store.getState().dispatch({ type: 'set_text', element_id: chatId, text: '保存期间又改了一次' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(save).toHaveBeenCalledTimes(1);

    const firstWrite = save.mock.calls[0];
    await act(async () => resolvers[0]({ revision: firstWrite[0] + 1, document: firstWrite[1] }));
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(save).toHaveBeenCalledTimes(2);
    expect(save.mock.calls[1][0]).toBe(firstWrite[0] + 1);
    await act(async () => resolvers[1]({ revision: firstWrite[0] + 2, document: save.mock.calls[1][1] }));
    expect(store.getState().saveStatus).toBe('saved');
  });
});
