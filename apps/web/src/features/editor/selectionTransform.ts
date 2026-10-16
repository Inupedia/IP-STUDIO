import type { CanvasElementV1 } from '@ip-studio/contracts/canvas';
import type { CanvasCommand } from './commands';

export interface ElementTransformSnapshot {
  element_id: string;
  x: number;
  y: number;
  scaleX: number;
  scaleY: number;
  rotation: number;
}

type TransformUpdate = { element_id: string; transform: CanvasElementV1['transform'] };

export interface GroupDragTracker {
  primary_element_id: string;
  element_ids: ReadonlySet<string>;
  ended_element_ids: ReadonlySet<string>;
  committed: boolean;
}

export function createGroupDragTracker(primaryElementId: string, elementIds: readonly string[]): GroupDragTracker {
  return {
    primary_element_id: primaryElementId,
    element_ids: new Set(elementIds),
    ended_element_ids: new Set(),
    committed: false,
  };
}

export function trackGroupDragEnd(
  tracker: GroupDragTracker,
  elementId: string,
): { tracker: GroupDragTracker; shouldCommit: boolean; finished: boolean } {
  if (!tracker.element_ids.has(elementId)) return { tracker, shouldCommit: false, finished: false };
  const ended = new Set(tracker.ended_element_ids);
  ended.add(elementId);
  const shouldCommit = elementId === tracker.primary_element_id && !tracker.committed;
  const nextTracker = {
    ...tracker,
    ended_element_ids: ended,
    committed: tracker.committed || shouldCommit,
  };
  return {
    tracker: nextTracker,
    shouldCommit,
    finished: ended.size >= tracker.element_ids.size,
  };
}

export function selectionTransformCommand(transforms: readonly TransformUpdate[]): CanvasCommand | null {
  if (transforms.length === 0) return null;
  if (transforms.length === 1) {
    const [transform] = transforms;
    return { type: 'set_transform', element_id: transform.element_id, transform: transform.transform };
  }
  return { type: 'set_transforms', transforms: [...transforms] };
}

export function collectSelectionTransforms(
  elements: readonly CanvasElementV1[],
  snapshots: readonly ElementTransformSnapshot[],
): Array<{ element_id: string; transform: CanvasElementV1['transform'] }> {
  const elementsById = new Map(elements.map((element) => [element.id, element]));
  return snapshots.flatMap((snapshot) => {
    const element = elementsById.get(snapshot.element_id);
    if (!element || element.locked) return [];
    return [{
      element_id: element.id,
      transform: {
        ...element.transform,
        x: snapshot.x,
        y: snapshot.y,
        width: Math.max(1, element.transform.width * snapshot.scaleX),
        height: Math.max(1, element.transform.height * snapshot.scaleY),
        rotation: snapshot.rotation,
      },
    }];
  });
}
