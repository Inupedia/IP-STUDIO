import { describe, expect, it } from 'vitest';
import fixture from '../../../../../packages/contracts/fixtures/canvas-v1.json';
import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import {
  collectSelectionTransforms,
  createGroupDragTracker,
  selectionTransformCommand,
  trackGroupDragEnd,
} from './selectionTransform';

const document = CanvasDocumentV1Schema.parse(fixture);

describe('collectSelectionTransforms', () => {
  it('converts selected node snapshots into one complete atomic transform set', () => {
    const elements = document.pages[0].panels[0].elements.map((element) => ({ ...element, locked: false }));
    const result = collectSelectionTransforms(elements, [
      { element_id: elements[0].id, x: 140, y: 80, scaleX: 1.5, scaleY: 0.5, rotation: 12 },
      { element_id: elements[1].id, x: 320, y: 90, scaleX: 2, scaleY: 1.25, rotation: -8 },
    ]);

    expect(result).toEqual([
      {
        element_id: elements[0].id,
        transform: { ...elements[0].transform, x: 140, y: 80, width: elements[0].transform.width * 1.5, height: elements[0].transform.height * 0.5, rotation: 12 },
      },
      {
        element_id: elements[1].id,
        transform: { ...elements[1].transform, x: 320, y: 90, width: elements[1].transform.width * 2, height: elements[1].transform.height * 1.25, rotation: -8 },
      },
    ]);
  });

  it('ignores locked or removed elements and clamps dimensions to at least one pixel', () => {
    const elements = document.pages[0].panels[0].elements;
    const editableElement = { ...elements[0], locked: false };
    const result = collectSelectionTransforms([editableElement], [
      { element_id: editableElement.id, x: 10, y: 20, scaleX: 0, scaleY: 0, rotation: 0 },
      { element_id: 'missing-element', x: 0, y: 0, scaleX: 1, scaleY: 1, rotation: 0 },
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].transform.width).toBe(1);
    expect(result[0].transform.height).toBe(1);
    expect(collectSelectionTransforms(elements, [
      { element_id: elements[0].id, x: 10, y: 20, scaleX: 1, scaleY: 1, rotation: 0 },
    ])).toEqual([]);
  });

  it('uses the single-element command for one selection and the atomic batch command for groups', () => {
    const elements = document.pages[0].panels[0].elements.map((element) => ({ ...element, locked: false }));
    const snapshots = elements.slice(0, 2).map((element) => ({
      element_id: element.id,
      x: element.transform.x + 10,
      y: element.transform.y + 5,
      scaleX: 1,
      scaleY: 1,
      rotation: element.transform.rotation,
    }));
    const transforms = collectSelectionTransforms(elements, snapshots);

    expect(selectionTransformCommand([])).toBeNull();
    expect(selectionTransformCommand(transforms.slice(0, 1))).toEqual({
      type: 'set_transform',
      element_id: transforms[0].element_id,
      transform: transforms[0].transform,
    });
    expect(selectionTransformCommand(transforms)).toEqual({ type: 'set_transforms', transforms });
  });

  it('commits a multi-select drag only once after the initiating node ends', () => {
    const tracker = createGroupDragTracker('primary', ['primary', 'secondary']);
    const secondaryEnded = trackGroupDragEnd(tracker, 'secondary');
    expect(secondaryEnded.shouldCommit).toBe(false);
    expect(secondaryEnded.finished).toBe(false);

    const primaryEnded = trackGroupDragEnd(secondaryEnded.tracker, 'primary');
    expect(primaryEnded.shouldCommit).toBe(true);
    expect(primaryEnded.finished).toBe(true);

    const duplicatePrimaryEnd = trackGroupDragEnd(primaryEnded.tracker, 'primary');
    expect(duplicatePrimaryEnd.shouldCommit).toBe(false);
    expect(duplicatePrimaryEnd.finished).toBe(true);
  });
});
