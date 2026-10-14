import { CanvasDocumentV1Schema } from '@ip-studio/contracts/canvas';
import type { CanvasDocumentV1, CanvasElementV1 } from '@ip-studio/contracts/canvas';
import type { LayoutTemplate } from '@ip-studio/contracts/layout';
import { applyLayout } from '@ip-studio/contracts/layout';

export type CanvasCommand =
  | { type: 'set_text'; element_id: string; text: string }
  | { type: 'set_dynamic_field'; field: 'title' | 'episode_number'; value: string }
  | { type: 'replace_image'; element_id: string; asset_version_id: string }
  | { type: 'set_crop'; element_id: string; crop: { x: number; y: number; width: number; height: number } }
  | { type: 'set_transform'; element_id: string; transform: CanvasElementV1['transform'] }
  | { type: 'set_transforms'; transforms: Array<{ element_id: string; transform: CanvasElementV1['transform'] }> }
  | { type: 'set_layout'; page_id: string; layout: LayoutTemplate }
  | { type: 'delete_element'; element_id: string }
  | { type: 'add_element'; panel_id: string; element: CanvasElementV1 };

function findElement(document: CanvasDocumentV1, id: string): CanvasElementV1 | undefined {
  return document.pages.flatMap((page) => page.panels.flatMap((panel) => panel.elements))
    .find((element) => element.id === id);
}

function assertUnlocked(document: CanvasDocumentV1, elementId: string): CanvasElementV1 {
  const element = findElement(document, elementId);
  if (!element) throw new Error(`Canvas element ${elementId} does not exist`);
  if (element.locked) throw new Error(`Canvas element ${elementId} is locked`);
  return element;
}

function withElementText(element: CanvasElementV1, text: string): CanvasElementV1 {
  switch (element.type) {
    case 'text':
      return { ...element, props: { ...element.props, text } };
    case 'chat_message':
      return { ...element, props: { ...element.props, text } };
    case 'speech_bubble':
      return { ...element, props: { ...element.props, text } };
    case 'thought_bubble':
      return { ...element, props: { ...element.props, text } };
    default:
      return element;
  }
}

export function applyCanvasCommand(document: CanvasDocumentV1, command: CanvasCommand): CanvasDocumentV1 {
  let next: CanvasDocumentV1;
  switch (command.type) {
    case 'set_dynamic_field':
      next = {
        ...document,
        dynamic_fields: { ...document.dynamic_fields, [command.field]: command.value },
      };
      break;
    case 'set_text': {
      const element = assertUnlocked(document, command.element_id);
      if (element.type === 'image' || element.type === 'sticker' || element.type === 'shape' || element.type === 'panel_frame') {
        throw new Error(`Canvas element ${command.element_id} does not contain editable text`);
      }
      next = {
        ...document,
        pages: document.pages.map((page) => ({
          ...page,
          panels: page.panels.map((panel) => ({
            ...panel,
            elements: panel.elements.map((candidate) => candidate.id === command.element_id
              ? withElementText(element, command.text)
              : candidate),
          })),
        })),
      };
      break;
    }
    case 'set_crop': {
      const element = assertUnlocked(document, command.element_id);
      if (element.type !== 'image') throw new Error(`Canvas element ${command.element_id} is not a cropped image`);
      next = {
        ...document,
        pages: document.pages.map((page) => ({
          ...page,
          panels: page.panels.map((panel) => ({
            ...panel,
            elements: panel.elements.map((candidate) => candidate.id === command.element_id
              ? { ...candidate, crop: command.crop }
              : candidate),
          })),
        })),
      };
      break;
    }
    case 'replace_image': {
      const element = assertUnlocked(document, command.element_id);
      if (element.type !== 'image' && element.type !== 'sticker') {
        throw new Error(`Canvas element ${command.element_id} is not an image`);
      }
      next = {
        ...document,
        pages: document.pages.map((page) => ({
          ...page,
          panels: page.panels.map((panel) => ({
            ...panel,
            elements: panel.elements.map((candidate) => candidate.id === command.element_id
              ? { ...candidate, asset_version_id: command.asset_version_id }
              : candidate),
          })),
        })),
      };
      break;
    }
    case 'set_transform': {
      assertUnlocked(document, command.element_id);
      next = {
        ...document,
        pages: document.pages.map((page) => ({
          ...page,
          panels: page.panels.map((panel) => ({
            ...panel,
            elements: panel.elements.map((candidate) => candidate.id === command.element_id
              ? { ...candidate, transform: command.transform }
              : candidate),
          })),
        })),
      };
      break;
    }
    case 'set_transforms': {
      const selectedIds = new Set<string>();
      for (const update of command.transforms) {
        if (selectedIds.has(update.element_id)) throw new Error(`Canvas element ${update.element_id} is selected more than once`);
        assertUnlocked(document, update.element_id);
        selectedIds.add(update.element_id);
      }
      if (command.transforms.length < 2) throw new Error('Group transform requires at least two canvas elements');
      const transforms = new Map(command.transforms.map((update) => [update.element_id, update.transform]));
      next = {
        ...document,
        pages: document.pages.map((page) => ({
          ...page,
          panels: page.panels.map((panel) => ({
            ...panel,
            elements: panel.elements.map((candidate) => {
              const transform = transforms.get(candidate.id);
              return transform ? { ...candidate, transform } : candidate;
            }),
          })),
        })),
      };
      break;
    }
    case 'delete_element': {
      assertUnlocked(document, command.element_id);
      next = {
        ...document,
        pages: document.pages.map((page) => ({
          ...page,
          panels: page.panels.map((panel) => ({
            ...panel,
            elements: panel.elements.filter((candidate) => candidate.id !== command.element_id),
          })),
        })),
      };
      break;
    }
    case 'add_element': {
      if (findElement(document, command.element.id)) throw new Error(`Canvas element ${command.element.id} already exists`);
      const matchingPanels = document.pages.flatMap((page) => page.panels)
        .filter((panel) => panel.id === command.panel_id);
      if (matchingPanels.length !== 1) throw new Error(`Canvas panel ${command.panel_id} is missing or ambiguous`);
      next = {
        ...document,
        pages: document.pages.map((page) => ({
          ...page,
          panels: page.panels.map((panel) => panel.id === command.panel_id
            ? { ...panel, elements: [...panel.elements, command.element] }
            : panel),
        })),
      };
      break;
    }
    case 'set_layout': {
      const page = document.pages.find((candidate) => candidate.id === command.page_id);
      if (!page) throw new Error(`Canvas page ${command.page_id} does not exist`);
      const flatPage = {
        brand_template_version_id: page.brand_template_version_id,
        panels: page.panels.map((panel) => ({
          panel_id: panel.id,
          ...panel.rect,
          elements: panel.elements,
        })),
      };
      const updated = applyLayout(flatPage, command.layout);
      const panels = updated.panels.map((panel, index) => {
        const previous = page.panels.find((candidate) => candidate.id === panel.panel_id) ?? page.panels[index];
        return {
          id: previous?.id ?? crypto.randomUUID(),
          rect: { x: panel.x, y: panel.y, width: panel.width, height: panel.height },
          elements: (previous?.elements as CanvasElementV1[] | undefined) ?? [],
        };
      });
      next = {
        ...document,
        pages: document.pages.map((candidate) => candidate.id === page.id
          ? { ...candidate, layout_code: command.layout.code, panels }
          : candidate),
      };
      break;
    }
  }
  return CanvasDocumentV1Schema.parse(next);
}
