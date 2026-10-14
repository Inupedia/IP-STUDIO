import { useEffect, useMemo, useState, type FormEvent } from 'react';
import type { AssetType, AssetVersion, IP } from '@ip-studio/contracts/domain';

export interface AssetLibraryApi {
  getAssets: (ipId: string) => Promise<AssetVersion[]>;
  uploadAsset: (
    file: File,
    ipId: string,
    name: string,
    type: AssetType,
    rightsNote?: string,
  ) => Promise<AssetVersion>;
  approveAssetVersion: (
    ipId: string,
    assetId: string,
    versionId: string,
  ) => Promise<AssetVersion>;
  getAssetPreview?: (ipId: string, assetId: string, versionId: string) => Promise<string>;
}

interface AssetLibraryProps {
  api: AssetLibraryApi;
  ips: IP[];
  selectedIpId: string;
  onSelectIp: (ipId: string) => void;
}

const assetTypes: { value: AssetType; label: string }[] = [
  { value: 'character_reference', label: '角色参考' },
  { value: 'character_pose', label: '角色动作' },
  { value: 'expression', label: '表情' },
  { value: 'scene', label: '场景' },
  { value: 'background', label: '背景' },
  { value: 'prop', label: '道具' },
  { value: 'composite_panel', label: '画格合成图' },
  { value: 'texture', label: '纹理' },
  { value: 'other', label: '其他' },
];

const statusLabels = {
  candidate: '候选',
  approved: '已批准',
  archived: '已归档',
} as const;

function formatBytes(byteSize: number): string {
  if (byteSize < 1024) return `${byteSize} B`;
  if (byteSize < 1024 * 1024) return `${(byteSize / 1024).toFixed(0)} KB`;
  return `${(byteSize / (1024 * 1024)).toFixed(1)} MB`;
}

export function AssetLibrary({ api, ips, selectedIpId, onSelectIp }: AssetLibraryProps) {
  const [assets, setAssets] = useState<AssetVersion[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [assetType, setAssetType] = useState<AssetType>('character_reference');
  const [rightsNote, setRightsNote] = useState('');
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!selectedIpId) {
      setAssets([]);
      return;
    }
    let active = true;
    setLoading(true);
    setError('');
    setAssets([]);
    api.getAssets(selectedIpId)
      .then((result) => {
        if (active) setAssets(result.filter((asset) => asset.owner_ip_id === selectedIpId));
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : '无法加载素材');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api, selectedIpId]);

  useEffect(() => {
    if (!api.getAssetPreview || assets.length === 0) {
      setPreviews({});
      return;
    }
    let active = true;
    const createdUrls: string[] = [];
    void Promise.all(
      assets.map(async (asset) => {
        try {
          const url = await api.getAssetPreview!(
            asset.owner_ip_id,
            asset.asset_id,
            asset.asset_version_id,
          );
          if (!active) {
            URL.revokeObjectURL(url);
            return null;
          }
          createdUrls.push(url);
          return [asset.asset_version_id, url] as const;
        } catch {
          return null;
        }
      }),
    ).then((results) => {
      if (active) setPreviews(Object.fromEntries(results.filter(Boolean) as [string, string][]));
    });
    return () => {
      active = false;
      createdUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [api, assets]);

  const visibleAssets = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase();
    return assets.filter((asset) => {
      const matchesSearch = !normalizedSearch || asset.name.toLocaleLowerCase().includes(normalizedSearch);
      const matchesStatus = !statusFilter || asset.status === statusFilter;
      const matchesType = !typeFilter || asset.type === typeFilter;
      return matchesSearch && matchesStatus && matchesType;
    });
  }, [assets, search, statusFilter, typeFilter]);

  async function refreshAssets() {
    if (!selectedIpId) return;
    const result = await api.getAssets(selectedIpId);
    setAssets(result.filter((asset) => asset.owner_ip_id === selectedIpId));
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !selectedIpId || !name.trim()) return;
    const fileInput = event.currentTarget.elements.namedItem('asset-file');
    setUploading(true);
    setError('');
    try {
      await api.uploadAsset(file, selectedIpId, name.trim(), assetType, rightsNote || undefined);
      setFile(null);
      setName('');
      setRightsNote('');
      if (fileInput instanceof HTMLInputElement) fileInput.value = '';
      await refreshAssets();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '素材上传失败');
    } finally {
      setUploading(false);
    }
  }

  async function approve(asset: AssetVersion) {
    setError('');
    try {
      await api.approveAssetVersion(selectedIpId, asset.asset_id, asset.asset_version_id);
      await refreshAssets();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '素材审批失败');
    }
  }

  const currentIp = ips.find((ip) => ip.id === selectedIpId);

  return (
    <section className="feature-panel" aria-labelledby="assets-title">
      <header className="feature-heading">
        <div>
          <p className="eyebrow">原始素材与锁定版本</p>
          <h2 id="assets-title">素材库</h2>
          <p className="section-copy">每份图片以原始文件保存；引用时使用明确的素材版本。</p>
        </div>
        <label className="ip-switcher">
          当前 IP
          <select value={selectedIpId} onChange={(event) => onSelectIp(event.currentTarget.value)}>
            {ips.map((ip) => <option key={ip.id} value={ip.id}>{ip.name}</option>)}
          </select>
        </label>
      </header>

      <form className="upload-panel" onSubmit={submitUpload}>
        <div className="upload-intro">
          <span className="upload-icon" aria-hidden="true">↥</span>
          <div>
            <h3>导入图片素材</h3>
            <p>支持 PNG、JPEG、WebP，单张不超过 25 MB。</p>
          </div>
        </div>
        <div className="upload-fields">
          <label className="file-picker">
            <span>选择图片</span>
            <input
              name="asset-file"
              aria-label="选择图片文件"
              type="file"
              accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
              onChange={(event) => {
                const selectedFile = event.currentTarget.files?.[0] ?? null;
                setFile(selectedFile);
                if (selectedFile && !name) {
                  setName(selectedFile.name.replace(/\.[^.]+$/, ''));
                }
              }}
            />
            <span className="file-name">{file?.name ?? '尚未选择文件'}</span>
          </label>
          <label>
            素材名称
            <input
              aria-label="素材名称"
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
              placeholder="例如：卡仔标准参考图"
            />
          </label>
          <label>
            素材类型
            <select
              aria-label="素材类型"
              value={assetType}
              onChange={(event) => setAssetType(event.currentTarget.value as AssetType)}
            >
              {assetTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
            </select>
          </label>
          <label>
            来源与许可备注
            <input
              aria-label="来源与许可备注"
              maxLength={4000}
              value={rightsNote}
              onChange={(event) => setRightsNote(event.currentTarget.value)}
              placeholder="可留空"
            />
          </label>
          <button className="button button-primary upload-submit" type="submit" disabled={!file || uploading}>
            {uploading ? '正在导入…' : '导入为候选素材'}
          </button>
        </div>
      </form>

      <div className="library-toolbar">
        <label className="search-field">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="搜索素材"
            value={search}
            onChange={(event) => setSearch(event.currentTarget.value)}
            placeholder="搜索名称"
          />
        </label>
        <label>
          状态
          <select aria-label="状态筛选" value={statusFilter} onChange={(event) => setStatusFilter(event.currentTarget.value)}>
            <option value="">全部状态</option>
            <option value="candidate">候选</option>
            <option value="approved">已批准</option>
            <option value="archived">已归档</option>
          </select>
        </label>
        <label>
          类型
          <select aria-label="类型筛选" value={typeFilter} onChange={(event) => setTypeFilter(event.currentTarget.value)}>
            <option value="">全部类型</option>
            {assetTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
          </select>
        </label>
        <span className="asset-count">{visibleAssets.length} 项</span>
      </div>

      {error && <p className="inline-error" role="alert">{error}</p>}
      {loading ? (
        <div className="list-message" role="status">正在读取 {currentIp?.name ?? 'IP'} 的素材…</div>
      ) : visibleAssets.length ? (
        <div className="asset-grid">
          {visibleAssets.map((asset) => (
            <article className="asset-card" aria-label={asset.name} key={asset.asset_version_id}>
              <div className="asset-preview">
                {previews[asset.asset_version_id] ? (
                  <img src={previews[asset.asset_version_id]} alt={`${asset.name} 预览`} />
                ) : (
                  <span aria-hidden="true">{asset.mime.replace('image/', '').toUpperCase()}</span>
                )}
                {asset.alpha && <span className="alpha-flag">透明</span>}
              </div>
              <div className="asset-card-copy">
                <div className="asset-card-title-row">
                  <h3>{asset.name}</h3>
                  <span className={`status-pill status-${asset.status}`}>{statusLabels[asset.status]}</span>
                </div>
                <p>{asset.width} × {asset.height} · {formatBytes(asset.byte_size)}</p>
                <p className="asset-version-note">v{asset.version_no} · SHA {asset.sha256.slice(0, 10)}</p>
                {asset.status === 'candidate' && (
                  <button className="button button-quiet approve-button" type="button" onClick={() => void approve(asset)}>
                    批准此版本
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-library">
          <span className="empty-library-mark" aria-hidden="true">◇</span>
          <div>
            <h3>{assets.length ? '没有符合条件的素材' : `${currentIp?.name ?? '当前 IP'} 还没有素材`}</h3>
            <p>{assets.length ? '试试调整搜索词或筛选条件。' : '导入标准参考图、表情或场景背景，作为后续分镜的可追溯素材。'}</p>
          </div>
        </div>
      )}
    </section>
  );
}
