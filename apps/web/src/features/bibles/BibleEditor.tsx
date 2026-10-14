import { useEffect, useMemo, useState, type FormEvent } from 'react';
import type {
  AssetVersion,
  Character,
  CharacterBible,
  CharacterVersion,
  IP,
  Style,
  StyleBible,
  StyleVersion,
} from '@ip-studio/contracts/domain';

export interface BibleEditorApi {
  getAssets: (ipId: string) => Promise<AssetVersion[]>;
  getCharacters: (ipId: string) => Promise<Character[]>;
  getStyles: (ipId: string) => Promise<Style[]>;
  createCharacter: (
    ipId: string,
    payload: { code: string; name: string; bible: CharacterBible },
  ) => Promise<CharacterVersion>;
  createCharacterVersion: (
    characterId: string,
    payload: { base_version_id?: string; bible: CharacterBible },
  ) => Promise<CharacterVersion>;
  approveCharacterVersion: (versionId: string) => Promise<CharacterVersion>;
  createStyle: (ipId: string, payload: { name: string; bible: StyleBible }) => Promise<StyleVersion>;
  createStyleVersion: (
    styleId: string,
    payload: { base_version_id?: string; bible: StyleBible },
  ) => Promise<StyleVersion>;
  approveStyleVersion: (versionId: string) => Promise<StyleVersion>;
  setDefaultStyle: (
    ipId: string,
    styleVersionId: string,
  ) => Promise<{ ip_id: string; default_style_version_id: string }>;
}

interface BibleEditorProps {
  api: BibleEditorApi;
  ip: IP;
  onDefaultStyleSet: (versionId: string) => void;
}

function StatusPill({ status }: { status: string }) {
  const labels: Record<string, string> = { candidate: '候选', approved: '已批准', archived: '已归档' };
  return <span className={`status-pill status-${status}`}>{labels[status] ?? status}</span>;
}

function splitLines(value: string): string[] {
  return value.split('\n').map((line) => line.trim()).filter(Boolean);
}

function paletteFromText(value: string): Record<string, string> {
  return Object.fromEntries(
    splitLines(value)
      .map((line) => {
        const separator = line.indexOf('=');
        return separator < 1 ? null : [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
      })
      .filter((entry): entry is [string, string] => Boolean(entry?.[0] && entry[1])),
  );
}

function paletteToText(palette: Record<string, string> | undefined): string {
  return Object.entries(palette ?? {}).map(([key, value]) => `${key}=${value}`).join('\n');
}

function ReferencePicker({
  assets,
  selected,
  onChange,
  label,
}: {
  assets: AssetVersion[];
  selected: string[];
  onChange: (value: string[]) => void;
  label: string;
}) {
  const approvedAssets = assets.filter((asset) => asset.status === 'approved');
  if (approvedAssets.length === 0) {
    return <p className="reference-hint">先在素材库批准参考图，之后可以把它锁定到此版本。</p>;
  }
  return (
    <fieldset className="reference-picker">
      <legend>{label}</legend>
      {approvedAssets.map((asset) => (
        <label key={asset.asset_version_id} className="checkbox-row">
          <input
            type="checkbox"
            checked={selected.includes(asset.asset_version_id)}
            onChange={(event) => {
              const next = event.currentTarget.checked
                ? [...selected, asset.asset_version_id]
                : selected.filter((id) => id !== asset.asset_version_id);
              onChange(next);
            }}
          />
          <span>{asset.name} <small>v{asset.version_no}</small></span>
        </label>
      ))}
    </fieldset>
  );
}

export function BibleEditor({ api, ip, onDefaultStyleSet }: BibleEditorProps) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [styles, setStyles] = useState<Style[]>([]);
  const [assets, setAssets] = useState<AssetVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [characterCode, setCharacterCode] = useState('');
  const [characterName, setCharacterName] = useState('');
  const [personality, setPersonality] = useState('');
  const [languageStyle, setLanguageStyle] = useState('');
  const [appearance, setAppearance] = useState('');
  const [invariants, setInvariants] = useState('');
  const [characterPalette, setCharacterPalette] = useState('');
  const [prohibitedFeatures, setProhibitedFeatures] = useState('');
  const [characterReferences, setCharacterReferences] = useState<string[]>([]);
  const [expressionReferences, setExpressionReferences] = useState<string[]>([]);
  const [poseReferences, setPoseReferences] = useState<string[]>([]);
  const [costumeReferences, setCostumeReferences] = useState<string[]>([]);
  const [characterSource, setCharacterSource] = useState<{
    characterId: string;
    version: CharacterVersion;
  } | null>(null);
  const [styleName, setStyleName] = useState('');
  const [linework, setLinework] = useState('');
  const [stylePalette, setStylePalette] = useState('');
  const [lighting, setLighting] = useState('');
  const [materials, setMaterials] = useState('');
  const [aspectRatios, setAspectRatios] = useState('');
  const [positiveRules, setPositiveRules] = useState('');
  const [negativeRules, setNegativeRules] = useState('');
  const [fontRules, setFontRules] = useState('');
  const [speechBubbleRules, setSpeechBubbleRules] = useState('');
  const [styleReferences, setStyleReferences] = useState<string[]>([]);
  const [styleSource, setStyleSource] = useState<{ styleId: string; version: StyleVersion } | null>(null);
  const [defaultStyleVersionId, setDefaultStyleVersionId] = useState(ip.default_style_version_id ?? '');
  const [saving, setSaving] = useState(false);

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const [nextCharacters, nextStyles, nextAssets] = await Promise.all([
        api.getCharacters(ip.id),
        api.getStyles(ip.id),
        api.getAssets(ip.id),
      ]);
      setCharacters(nextCharacters);
      setStyles(nextStyles);
      setAssets(nextAssets.filter((asset) => asset.owner_ip_id === ip.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法读取角色与画风规范');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setDefaultStyleVersionId(ip.default_style_version_id ?? '');
    void refresh();
  }, [ip.id]);

  const approvedStyleVersions = useMemo(
    () => styles.flatMap((style) => style.versions
      .filter((version) => version.status === 'approved')
      .map((version) => ({ style, version }))),
    [styles],
  );

  async function submitCharacter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError('');
    const bible: CharacterBible = {
      personality,
      language_style: languageStyle,
      fixed_appearance: appearance,
      invariants: splitLines(invariants),
      palette: paletteFromText(characterPalette),
      prohibited_features: splitLines(prohibitedFeatures),
      standard_reference_asset_version_ids: characterReferences,
      expression_asset_version_ids: expressionReferences,
      pose_asset_version_ids: poseReferences,
      costume_asset_version_ids: costumeReferences,
    };
    try {
      if (characterSource) {
        await api.createCharacterVersion(characterSource.characterId, {
          base_version_id: characterSource.version.character_version_id,
          bible,
        });
      } else {
        await api.createCharacter(ip.id, { code: characterCode, name: characterName, bible });
        setCharacterCode('');
        setCharacterName('');
      }
      setCharacterSource(null);
      setPersonality('');
      setLanguageStyle('');
      setAppearance('');
      setInvariants('');
      setCharacterPalette('');
      setProhibitedFeatures('');
      setCharacterReferences([]);
      setExpressionReferences([]);
      setPoseReferences([]);
      setCostumeReferences([]);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '角色候选保存失败');
    } finally {
      setSaving(false);
    }
  }

  function deriveCharacter(characterId: string, version: CharacterVersion) {
    setCharacterSource({ characterId, version });
    setPersonality(version.bible.personality ?? '');
    setLanguageStyle(version.bible.language_style ?? '');
    setAppearance(version.bible.fixed_appearance ?? '');
    setInvariants(version.bible.invariants?.join('\n') ?? '');
    setCharacterPalette(paletteToText(version.bible.palette));
    setProhibitedFeatures(version.bible.prohibited_features?.join('\n') ?? '');
    setCharacterReferences(version.bible.standard_reference_asset_version_ids ?? []);
    setExpressionReferences(version.bible.expression_asset_version_ids ?? []);
    setPoseReferences(version.bible.pose_asset_version_ids ?? []);
    setCostumeReferences(version.bible.costume_asset_version_ids ?? []);
  }

  async function approveCharacter(versionId: string) {
    try {
      await api.approveCharacterVersion(versionId);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '角色版本审批失败');
    }
  }

  async function submitStyle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError('');
    const bible: StyleBible = {
      linework_rules: splitLines(linework),
      palette: paletteFromText(stylePalette),
      lighting,
      materials: splitLines(materials),
      aspect_ratios: splitLines(aspectRatios),
      positive_rules: splitLines(positiveRules),
      negative_rules: splitLines(negativeRules),
      example_asset_version_ids: styleReferences,
      font_rules: fontRules,
      speech_bubble_rules: speechBubbleRules,
    };
    try {
      if (styleSource) {
        await api.createStyleVersion(styleSource.styleId, {
          base_version_id: styleSource.version.style_version_id,
          bible,
        });
      } else {
        await api.createStyle(ip.id, { name: styleName, bible });
        setStyleName('');
      }
      setStyleSource(null);
      setLinework('');
      setStylePalette('');
      setLighting('');
      setMaterials('');
      setAspectRatios('');
      setPositiveRules('');
      setNegativeRules('');
      setFontRules('');
      setSpeechBubbleRules('');
      setStyleReferences([]);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '画风候选保存失败');
    } finally {
      setSaving(false);
    }
  }

  function deriveStyle(styleId: string, version: StyleVersion) {
    setStyleSource({ styleId, version });
    setLinework(version.bible.linework_rules?.join('\n') ?? '');
    setStylePalette(paletteToText(version.bible.palette));
    setLighting(version.bible.lighting ?? '');
    setMaterials(version.bible.materials?.join('\n') ?? '');
    setAspectRatios(version.bible.aspect_ratios?.join('\n') ?? '');
    setPositiveRules(version.bible.positive_rules?.join('\n') ?? '');
    setNegativeRules(version.bible.negative_rules?.join('\n') ?? '');
    setFontRules(version.bible.font_rules ?? '');
    setSpeechBubbleRules(version.bible.speech_bubble_rules ?? '');
    setStyleReferences(version.bible.example_asset_version_ids ?? []);
  }

  async function approveStyle(versionId: string) {
    try {
      await api.approveStyleVersion(versionId);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '画风版本审批失败');
    }
  }

  async function saveDefaultStyle() {
    if (!defaultStyleVersionId) return;
    setSaving(true);
    setError('');
    try {
      await api.setDefaultStyle(ip.id, defaultStyleVersionId);
      onDefaultStyleSet(defaultStyleVersionId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '默认画风保存失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="feature-panel bible-workspace" aria-labelledby="bibles-title">
      <header className="feature-heading">
        <div>
          <p className="eyebrow">保持角色与画面的连续性</p>
          <h2 id="bibles-title">角色与画风</h2>
          <p className="section-copy">批准版本会锁定；调整规范时，从锁定版本派生新的候选。</p>
        </div>
        <div className="default-style-control">
          <label htmlFor="default-style">默认画风</label>
          <select
            id="default-style"
            value={defaultStyleVersionId}
            onChange={(event) => setDefaultStyleVersionId(event.currentTarget.value)}
          >
            <option value="">暂未设置</option>
            {approvedStyleVersions.map(({ style, version }) => (
              <option key={version.style_version_id} value={version.style_version_id}>
                {style.name} · v{version.version_no}
              </option>
            ))}
          </select>
          <button className="button button-quiet" type="button" disabled={!defaultStyleVersionId || saving} onClick={() => void saveDefaultStyle()}>
            保存默认画风
          </button>
        </div>
      </header>

      {error && <p className="inline-error" role="alert">{error}</p>}
      {loading ? <p className="list-message" role="status">正在读取规范…</p> : (
        <div className="bible-columns">
          <section className="bible-column" aria-labelledby="characters-heading">
            <div className="subsection-heading">
              <div>
                <p className="eyebrow">CHARACTER BIBLE</p>
                <h3 id="characters-heading">角色规范</h3>
              </div>
              <span className="subsection-count">{characters.length} 个角色</span>
            </div>
            <form className="bible-form" onSubmit={submitCharacter}>
              <div className="form-pair">
                <label>
                  编号
                  <input required maxLength={48} disabled={Boolean(characterSource)} value={characterSource ? characters.find((character) => character.character_id === characterSource.characterId)?.code ?? '' : characterCode} onChange={(event) => setCharacterCode(event.currentTarget.value)} placeholder="KAZI" />
                </label>
                <label>
                  名称
                  <input required maxLength={120} disabled={Boolean(characterSource)} value={characterSource ? characters.find((character) => character.character_id === characterSource.characterId)?.name ?? '' : characterName} onChange={(event) => setCharacterName(event.currentTarget.value)} placeholder="卡仔" />
                </label>
              </div>
              <label>
                性格
                <textarea rows={2} value={personality} onChange={(event) => setPersonality(event.currentTarget.value)} />
              </label>
              <label>
                语言风格
                <textarea rows={2} value={languageStyle} onChange={(event) => setLanguageStyle(event.currentTarget.value)} />
              </label>
              <label>
                固定外观
                <textarea rows={3} value={appearance} onChange={(event) => setAppearance(event.currentTarget.value)} />
              </label>
              <label>
                不可变化特征（每行一条）
                <textarea rows={2} value={invariants} onChange={(event) => setInvariants(event.currentTarget.value)} />
              </label>
              <label>
                主色板（每行填写 名称=#十六进制色值）
                <textarea rows={2} value={characterPalette} onChange={(event) => setCharacterPalette(event.currentTarget.value)} placeholder="主色=#4388C7" />
              </label>
              <label>
                禁忌特征（每行一条）
                <textarea rows={2} value={prohibitedFeatures} onChange={(event) => setProhibitedFeatures(event.currentTarget.value)} />
              </label>
              <ReferencePicker
                assets={assets}
                selected={characterReferences}
                onChange={setCharacterReferences}
                label="标准参考图（仅列出已批准素材）"
              />
              <ReferencePicker
                assets={assets}
                selected={expressionReferences}
                onChange={setExpressionReferences}
                label="表情素材"
              />
              <ReferencePicker
                assets={assets}
                selected={poseReferences}
                onChange={setPoseReferences}
                label="动作素材"
              />
              <ReferencePicker
                assets={assets}
                selected={costumeReferences}
                onChange={setCostumeReferences}
                label="服装素材"
              />
              {characterSource && (
                <button className="text-button" type="button" onClick={() => setCharacterSource(null)}>
                  取消派生
                </button>
              )}
              <button className="button button-primary" type="submit" disabled={saving}>
                {saving ? '正在保存…' : characterSource ? '保存角色候选版本' : '创建角色候选'}
              </button>
            </form>
            <div className="bible-records">
              {characters.map((character) => (
                <article className="bible-record" key={character.character_id}>
                  <div className="bible-record-heading">
                    <div><h4>{character.name}</h4><span>{character.code}</span></div>
                    <span>{character.versions.length} 个版本</span>
                  </div>
                  {character.versions.map((version) => (
                    <div className="version-item" key={version.character_version_id}>
                      <div className="version-row">
                        <span>v{version.version_no}</span>
                        <StatusPill status={version.status} />
                        {version.status === 'candidate' ? (
                          <button className="text-button" type="button" onClick={() => void approveCharacter(version.character_version_id)}>批准</button>
                        ) : version.status === 'approved' ? (
                          <button className="text-button" type="button" onClick={() => deriveCharacter(character.character_id, version)}>派生候选</button>
                        ) : null}
                      </div>
                      <details className="version-details">
                        <summary>查看版本内容</summary>
                        <div className="bible-snapshot">
                          <p><strong>性格：</strong>{version.bible.personality || '未填写'}</p>
                          <p><strong>语言风格：</strong>{version.bible.language_style || '未填写'}</p>
                          <p><strong>固定外观：</strong>{version.bible.fixed_appearance || '未填写'}</p>
                          <p><strong>不可变化：</strong>{version.bible.invariants?.join('、') || '未填写'}</p>
                          <p><strong>主色板：</strong>{Object.entries(version.bible.palette ?? {}).map(([key, color]) => `${key} ${color}`).join(' · ') || '未填写'}</p>
                          <p><strong>禁忌特征：</strong>{version.bible.prohibited_features?.join('、') || '未填写'}</p>
                          <p><strong>标准参考：</strong>{version.bible.standard_reference_asset_version_ids?.map((id) => assets.find((asset) => asset.asset_version_id === id)?.name ?? `版本 ${id.slice(0, 8)}`).join('、') || '未关联'}</p>
                          <p><strong>表情 / 动作 / 服装：</strong>{[
                            ...(version.bible.expression_asset_version_ids ?? []),
                            ...(version.bible.pose_asset_version_ids ?? []),
                            ...(version.bible.costume_asset_version_ids ?? []),
                          ].map((id) => assets.find((asset) => asset.asset_version_id === id)?.name ?? `版本 ${id.slice(0, 8)}`).join('、') || '未关联'}</p>
                        </div>
                      </details>
                    </div>
                  ))}
                </article>
              ))}
              {characters.length === 0 && <p className="muted-note">还没有角色。先建立一个候选版本，再审阅批准。</p>}
            </div>
          </section>

          <section className="bible-column" aria-labelledby="styles-heading">
            <div className="subsection-heading">
              <div>
                <p className="eyebrow">STYLE BIBLE</p>
                <h3 id="styles-heading">画风规范</h3>
              </div>
              <span className="subsection-count">{styles.length} 套画风</span>
            </div>
            <form className="bible-form" onSubmit={submitStyle}>
              <label>
                画风名称
                <input required maxLength={120} disabled={Boolean(styleSource)} value={styleSource ? styles.find((style) => style.style_id === styleSource.styleId)?.name ?? '' : styleName} onChange={(event) => setStyleName(event.currentTarget.value)} placeholder="温暖日常漫画" />
              </label>
              <label>
                线稿规则（每行一条）
                <textarea rows={3} value={linework} onChange={(event) => setLinework(event.currentTarget.value)} placeholder="粗细清晰，避免过度细碎" />
              </label>
              <label>
                配色（每行填写 名称=#十六进制色值）
                <textarea rows={2} value={stylePalette} onChange={(event) => setStylePalette(event.currentTarget.value)} placeholder="背景=#F4EAD7" />
              </label>
              <label>
                光影规则
                <textarea rows={2} value={lighting} onChange={(event) => setLighting(event.currentTarget.value)} />
              </label>
              <label>
                材质（每行一条）
                <textarea rows={2} value={materials} onChange={(event) => setMaterials(event.currentTarget.value)} />
              </label>
              <label>
                画幅比例（每行一条）
                <textarea rows={2} value={aspectRatios} onChange={(event) => setAspectRatios(event.currentTarget.value)} placeholder="3:4" />
              </label>
              <label>
                正向规范（每行一条）
                <textarea rows={2} value={positiveRules} onChange={(event) => setPositiveRules(event.currentTarget.value)} />
              </label>
              <label>
                负向规范（每行一条）
                <textarea rows={2} value={negativeRules} onChange={(event) => setNegativeRules(event.currentTarget.value)} />
              </label>
              <label>
                字体规则
                <textarea rows={2} value={fontRules} onChange={(event) => setFontRules(event.currentTarget.value)} />
              </label>
              <label>
                对话气泡规则
                <textarea rows={2} value={speechBubbleRules} onChange={(event) => setSpeechBubbleRules(event.currentTarget.value)} />
              </label>
              <ReferencePicker
                assets={assets}
                selected={styleReferences}
                onChange={setStyleReferences}
                label="画风示例图（仅列出已批准素材）"
              />
              {styleSource && (
                <button className="text-button" type="button" onClick={() => setStyleSource(null)}>
                  取消派生
                </button>
              )}
              <button className="button button-primary" type="submit" disabled={saving}>
                {saving ? '正在保存…' : styleSource ? '保存画风候选版本' : '创建画风候选'}
              </button>
            </form>
            <div className="bible-records">
              {styles.map((style) => (
                <article className="bible-record" key={style.style_id}>
                  <div className="bible-record-heading">
                    <h4>{style.name}</h4><span>{style.versions.length} 个版本</span>
                  </div>
                  {style.versions.map((version) => (
                    <div className="version-item" key={version.style_version_id}>
                      <div className="version-row">
                        <span>v{version.version_no}</span>
                        <StatusPill status={version.status} />
                        {version.status === 'candidate' ? (
                          <button className="text-button" type="button" onClick={() => void approveStyle(version.style_version_id)}>批准</button>
                        ) : version.status === 'approved' ? (
                          <button className="text-button" type="button" onClick={() => deriveStyle(style.style_id, version)}>派生候选</button>
                        ) : null}
                      </div>
                      <details className="version-details">
                        <summary>查看版本内容</summary>
                        <div className="bible-snapshot">
                          <p><strong>线稿：</strong>{version.bible.linework_rules?.join('、') || '未填写'}</p>
                          <p><strong>配色：</strong>{Object.entries(version.bible.palette ?? {}).map(([key, color]) => `${key} ${color}`).join(' · ') || '未填写'}</p>
                          <p><strong>光影：</strong>{version.bible.lighting || '未填写'}</p>
                          <p><strong>材质 / 比例：</strong>{[
                            ...(version.bible.materials ?? []),
                            ...(version.bible.aspect_ratios ?? []),
                          ].join('、') || '未填写'}</p>
                          <p><strong>正向规范：</strong>{version.bible.positive_rules?.join('、') || '未填写'}</p>
                          <p><strong>负向规范：</strong>{version.bible.negative_rules?.join('、') || '未填写'}</p>
                          <p><strong>字体：</strong>{version.bible.font_rules || '未填写'}</p>
                          <p><strong>气泡：</strong>{version.bible.speech_bubble_rules || '未填写'}</p>
                          <p><strong>示例素材：</strong>{version.bible.example_asset_version_ids?.map((id) => assets.find((asset) => asset.asset_version_id === id)?.name ?? `版本 ${id.slice(0, 8)}`).join('、') || '未关联'}</p>
                        </div>
                      </details>
                    </div>
                  ))}
                </article>
              ))}
              {styles.length === 0 && <p className="muted-note">还没有画风。建立候选并批准后，可设为此 IP 的默认画风。</p>}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
