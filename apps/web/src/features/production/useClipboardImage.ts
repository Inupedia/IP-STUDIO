import { useEffect, useRef, useState } from 'react';

export type ClipboardImageHandler = (targetPanelId: string, file: File) => void | Promise<void>;

export function useClipboardImage(
  targetPanelId: string | null,
  onPasteImage: ClipboardImageHandler,
) {
  const handlerRef = useRef(onPasteImage);
  const [error, setError] = useState('');

  useEffect(() => {
    handlerRef.current = onPasteImage;
  }, [onPasteImage]);

  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const item = Array.from(event.clipboardData?.items ?? []).find(
        (candidate) => candidate.kind === 'file' && candidate.type.startsWith('image/'),
      );
      if (!item) return;
      const file = item.getAsFile();
      if (!file) return;
      event.preventDefault();
      setError('');
      if (!targetPanelId) {
        setError('请先在画布中选择目标画格，再粘贴图片。');
        return;
      }
      void Promise.resolve(handlerRef.current(targetPanelId, file)).catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : '无法读取剪贴板图片');
      });
    }

    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [targetPanelId]);

  return { error, clearError: () => setError('') };
}
