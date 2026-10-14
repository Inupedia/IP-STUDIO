import { useEffect } from 'react';
import { createStore, type StoreApi } from 'zustand/vanilla';
import { useStore } from 'zustand';
import type { CanvasDocumentV1 } from '@ip-studio/contracts/canvas';
import { applyCanvasCommand, type CanvasCommand } from './commands';

export type SaveStatus = 'saved' | 'dirty' | 'saving' | 'conflict' | 'error';

export interface DocumentEditorState {
  document: CanvasDocumentV1;
  revision: number;
  past: CanvasDocumentV1[];
  future: CanvasDocumentV1[];
  isDirty: boolean;
  saveStatus: SaveStatus;
  error: string | null;
  dispatch: (command: CanvasCommand) => void;
  undo: () => void;
  redo: () => void;
  markSaveStarted: () => void;
  markSaved: (revision: number, savedDocument: CanvasDocumentV1) => void;
  markConflict: (message: string) => void;
  markError: (message: string) => void;
  replaceDocument: (document: CanvasDocumentV1, revision: number) => void;
}

export interface DocumentSaveResult {
  revision: number;
  document: CanvasDocumentV1;
}

export type SaveDocument = (
  baseRevision: number,
  document: CanvasDocumentV1,
) => Promise<DocumentSaveResult>;

const MAX_HISTORY = 50;

export function createDocumentStore(document: CanvasDocumentV1): StoreApi<DocumentEditorState> {
  return createStore<DocumentEditorState>((set, get) => ({
    document,
    revision: document.revision,
    past: [],
    future: [],
    isDirty: false,
    saveStatus: 'saved',
    error: null,
    dispatch: (command) => {
      const state = get();
      const nextDocument = applyCanvasCommand(state.document, command);
      set({
        document: nextDocument,
        past: [...state.past, state.document].slice(-MAX_HISTORY),
        future: [],
        isDirty: true,
        saveStatus: state.saveStatus === 'saving' ? 'saving' : 'dirty',
        error: null,
      });
    },
    undo: () => {
      const state = get();
      if (state.past.length === 0) return;
      const previous = state.past[state.past.length - 1];
      set({
        document: previous,
        past: state.past.slice(0, -1),
        future: [state.document, ...state.future].slice(0, MAX_HISTORY),
        isDirty: true,
        saveStatus: state.saveStatus === 'saving' ? 'saving' : 'dirty',
        error: null,
      });
    },
    redo: () => {
      const state = get();
      if (state.future.length === 0) return;
      const [next, ...future] = state.future;
      set({
        document: next,
        past: [...state.past, state.document].slice(-MAX_HISTORY),
        future,
        isDirty: true,
        saveStatus: state.saveStatus === 'saving' ? 'saving' : 'dirty',
        error: null,
      });
    },
    markSaveStarted: () => set({ saveStatus: 'saving', error: null }),
    markSaved: (revision, savedDocument) => {
      const state = get();
      const hasNewerEdits = state.document !== savedDocument;
      set({
        document: { ...state.document, revision },
        revision,
        isDirty: hasNewerEdits,
        saveStatus: hasNewerEdits ? 'dirty' : 'saved',
        error: null,
      });
    },
    markConflict: (message) => set({ isDirty: true, saveStatus: 'conflict', error: message }),
    markError: (message) => set({ isDirty: true, saveStatus: 'error', error: message }),
    replaceDocument: (nextDocument, revision) => set({
      document: nextDocument,
      revision,
      past: [],
      future: [],
      isDirty: false,
      saveStatus: 'saved',
      error: null,
    }),
  }));
}

export function useDocumentAutosave(
  store: StoreApi<DocumentEditorState>,
  saveDocument: SaveDocument,
  delayMs = 1500,
): void {
  const document = useStore(store, (state) => state.document);
  const revision = useStore(store, (state) => state.revision);
  const isDirty = useStore(store, (state) => state.isDirty);
  const saveStatus = useStore(store, (state) => state.saveStatus);

  useEffect(() => {
    if (!isDirty || saveStatus === 'conflict' || saveStatus === 'error' || saveStatus === 'saving') return;
    const timer = window.setTimeout(async () => {
      store.getState().markSaveStarted();
      try {
        const result = await saveDocument(revision, document);
        store.getState().markSaved(result.revision, document);
      } catch (cause) {
        const message = cause instanceof Error ? cause.message : '自动保存失败';
        if (typeof cause === 'object' && cause !== null && 'status' in cause && cause.status === 409) {
          store.getState().markConflict(message);
        } else {
          store.getState().markError(message);
        }
      }
    }, delayMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [document, isDirty, revision, saveDocument, saveStatus, store, delayMs]);
}
