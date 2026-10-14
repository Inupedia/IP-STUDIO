import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AssetLibrary, type AssetLibraryApi } from './AssetLibrary';
import type { AssetVersion, IP } from '../../../../../packages/contracts/src/domain';

const ips: IP[] = [
  {
    id: 'ip-a',
    code: 'LAG',
    name: '人间卡顿局',
    summary: null,
    status: 'active',
    default_style_version_id: null,
    created_at: '2026-10-14T00:00:00Z',
  },
  {
    id: 'ip-b',
    code: 'PENG',
    name: '噗噜的小日子',
    summary: null,
    status: 'active',
    default_style_version_id: null,
    created_at: '2026-10-14T00:00:00Z',
  },
];

const assetsByIp: Record<string, AssetVersion[]> = {
  'ip-a': [
    {
      asset_id: 'asset-a',
      asset_version_id: 'version-a',
      workspace_id: 'workspace-a',
      owner_ip_id: 'ip-a',
      type: 'character_reference',
      name: '卡仔标准参考图',
      status: 'candidate',
      version_no: 1,
      sha256: 'a'.repeat(64),
      mime: 'image/png',
      byte_size: 128,
      width: 2,
      height: 2,
      alpha: true,
      created_at: '2026-10-14T00:00:00Z',
    },
  ],
  'ip-b': [
    {
      asset_id: 'asset-b',
      asset_version_id: 'version-b',
      workspace_id: 'workspace-a',
      owner_ip_id: 'ip-b',
      type: 'background',
      name: '噗噜的卧室',
      status: 'approved',
      version_no: 2,
      sha256: 'b'.repeat(64),
      mime: 'image/webp',
      byte_size: 256,
      width: 4,
      height: 4,
      alpha: false,
      created_at: '2026-10-14T00:00:00Z',
    },
  ],
};

describe('AssetLibrary', () => {
  it('filters assets by the selected IP and reflects candidate status', async () => {
    const api: AssetLibraryApi = {
      getAssets: vi.fn(async (ipId) => assetsByIp[ipId] ?? []),
      uploadAsset: vi.fn(),
      approveAssetVersion: vi.fn(async () => assetsByIp['ip-a'][0]),
    };
    let selectedIpId = 'ip-a';
    const onSelectIp = vi.fn((ipId: string) => {
      selectedIpId = ipId;
      rerenderView();
    });
    let rerenderView = () => {};
    const renderResult = render(
      <AssetLibrary
        api={api}
        ips={ips}
        selectedIpId={selectedIpId}
        onSelectIp={onSelectIp}
      />,
    );
    rerenderView = () => {
      renderResult.rerender(
        <AssetLibrary
          api={api}
          ips={ips}
          selectedIpId={selectedIpId}
          onSelectIp={onSelectIp}
        />,
      );
    };

    expect(await screen.findByText('卡仔标准参考图')).toBeTruthy();
    expect(screen.queryByText('噗噜的卧室')).toBeNull();
    const firstAsset = screen.getByRole('article', { name: '卡仔标准参考图' });
    expect(within(firstAsset).getByText('候选')).toBeTruthy();
    expect(api.getAssets).toHaveBeenCalledWith('ip-a');
    fireEvent.click(within(firstAsset).getByRole('button', { name: '批准此版本' }));
    await waitFor(() => expect(api.approveAssetVersion).toHaveBeenCalledWith('ip-a', 'asset-a', 'version-a'));

    fireEvent.change(screen.getByLabelText('当前 IP'), { target: { value: 'ip-b' } });

    await waitFor(() => expect(api.getAssets).toHaveBeenLastCalledWith('ip-b'));
    expect(await screen.findByText('噗噜的卧室')).toBeTruthy();
    expect(screen.queryByText('卡仔标准参考图')).toBeNull();
    const assetCard = screen.getByRole('article', { name: '噗噜的卧室' });
    expect(within(assetCard).getByText('已批准')).toBeTruthy();
  });
});
