import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../lib/api';
import { CandidateReview } from './CandidateReview';

vi.mock('../../lib/api', () => ({
  api: {
    getGenerationCandidates: vi.fn(),
    getAssetPreview: vi.fn(),
    approveGenerationCandidate: vi.fn(),
    rejectGenerationCandidate: vi.fn(),
  },
}));

const candidate = {
  candidate_id: '10000000-0000-4000-8000-000000000001',
  task_id: '10000000-0000-4000-8000-000000000002',
  panel_id: '10000000-0000-4000-8000-000000000003',
  asset_id: '10000000-0000-4000-8000-000000000004',
  asset_version_id: '10000000-0000-4000-8000-000000000005',
  asset_name: '候选画格',
  asset_type: 'composite_panel',
  version_no: 1,
  mime: 'image/png' as const,
  sha256: 'a'.repeat(64),
  byte_size: 100,
  width: 3,
  height: 2,
  status: 'pending_review' as const,
  created_at: '2026-10-14T00:00:00Z',
  reviewed_at: null,
  reviewed_by_user_id: null,
  review_note: null,
};

describe('CandidateReview', () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.mocked(api.getGenerationCandidates).mockReset();
    vi.mocked(api.getAssetPreview).mockReset();
    vi.mocked(api.approveGenerationCandidate).mockReset();
    vi.mocked(api.rejectGenerationCandidate).mockReset();
  });

  it('records a rejection reason and keeps the rejected candidate in review history', async () => {
    vi.mocked(api.getGenerationCandidates).mockResolvedValue([candidate]);
    vi.mocked(api.getAssetPreview).mockResolvedValue('blob:candidate-preview');
    vi.mocked(api.rejectGenerationCandidate).mockResolvedValue({
      ...candidate,
      status: 'rejected',
      reviewed_at: '2026-10-14T00:10:00Z',
      reviewed_by_user_id: '10000000-0000-4000-8000-000000000099',
      review_note: '比例不对',
    });
    render(<CandidateReview ipId="10000000-0000-4000-8000-000000000010" onReviewed={vi.fn()} />);

    fireEvent.change(await screen.findByLabelText('拒绝原因 · 候选画格'), {
      target: { value: '比例不对' },
    });
    fireEvent.click(screen.getByRole('button', { name: '拒绝候选 · 候选画格' }));

    await waitFor(() => expect(api.rejectGenerationCandidate).toHaveBeenCalledWith(
      candidate.candidate_id,
      '比例不对',
    ));
    expect(await screen.findByText('已拒绝')).toBeTruthy();
    expect(screen.getByText('审核意见：比例不对')).toBeTruthy();
  });
});
