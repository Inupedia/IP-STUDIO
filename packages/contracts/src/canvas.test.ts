import { describe, expect, it } from 'vitest';
import fixture from '../fixtures/canvas-v1.json';
import { CanvasDocumentV1Schema, resolveMessageSide } from './canvas';

describe('CanvasDocumentV1', () => {
  it('parses the shared v1 fixture and requires an immutable brand version', () => {
    expect(CanvasDocumentV1Schema.parse(fixture).schema_version).toBe('1.0');
    const withoutBrand = { ...fixture, brand_template_version_id: undefined };
    expect(CanvasDocumentV1Schema.safeParse(withoutBrand).success).toBe(false);
  });

  it('derives chat direction from the sender identity', () => {
    const panel = fixture.pages[0].panels[0];
    const friend = panel.elements[1];
    const self = panel.elements[2];
    if (friend.type !== 'chat_message' || self.type !== 'chat_message') throw new Error('Invalid fixture');
    expect(resolveMessageSide(friend.props.sender_id, friend.props.self_participant_id)).toBe('left');
    expect(resolveMessageSide(self.props.sender_id, self.props.self_participant_id)).toBe('right');
  });

  it('rejects malformed asset version references', () => {
    const malformed = structuredClone(fixture);
    malformed.pages[0].panels[0].elements[0].asset_version_id = 'asset-not-a-uuid';
    expect(CanvasDocumentV1Schema.safeParse(malformed).success).toBe(false);
  });
});
