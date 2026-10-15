# Codex ImageGen capability matrix

Last checked: 2026-10-15 (Asia/Shanghai)

This is environment evidence, not a product-wide guarantee. IP Studio must repeat the read-only
runtime checks for its own process and requires an explicit administrator E2E probe before its API
reports `available`.

| Probe | Result | Evidence |
|---|---|---|
| Codex CLI installed | Yes | Stable CLI: `/opt/homebrew/bin/codex`, `codex-cli 0.162.1`; this is the latest stable release reported by the [official release page](https://github.com/openai/codex/releases). |
| Codex desktop app | Up to date | Codex app update check reported production version `26.1007.71326`, status `up_to_date`. |
| Desktop-bundled Codex CLI | Yes | `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`, `codex-cli 0.162.0-alpha.17.2`. |
| Cursor extension Codex CLI | Yes | `/Users/inupedia/.cursor/extensions/openai.chatgpt-26.908.40401-darwin-arm64/bin/macos-aarch64/codex`, `codex-cli 0.154.0-alpha.6.2`. |
| Codex login | Yes | Homebrew stable, desktop-bundled, and Cursor-bundled CLIs reported `Logged in using ChatGPT`; no token or cookie was read by IP Studio. |
| Local App Server | Yes | All three distinct CLIs initialized `codex app-server --listen stdio://` and answered `modelProvider/capabilities/read`. |
| Provider advertises ImageGen | Yes | All three App Servers reported `imageGeneration: true`; this is only capability advertisement, not successful inference. |
| Real native ImageGen output | Yes, for this local Codex session | An explicit `codex exec` call invoked native ImageGen, saved a PNG in the Codex-generated output directory, and copied it to `/tmp/ip-studio-imagegen-probe/probe.png` |
| PNG integrity | Passed | `file` identified PNG; Pillow `Image.verify()` and a full decode succeeded; 1254×1254 RGB, 1,627,707 bytes |
| IP Studio API-owned administrator probe (2026-10-14, PostgreSQL) | `unavailable` | Authenticated FastAPI requests confirmed `imageGeneration: true`, but the CLI did not record a successful native ImageGen event or bounded PNG; one retry exited `1`. The API correctly refused to mark the capability available, so no native run or candidate was created. |
| Follow-up isolated API probe (2026-10-14, SQLite) | Inconclusive | The authenticated request did not return a report and was manually interrupted. Its temporary directory was cleaned up; no event log or PNG was retained for verification. This attempt changes neither the earlier API result nor AC-25. |
| Desktop-bundled CLI API probe (2026-10-15, SQLite) | `unavailable` | The authenticated `POST /api/v1/codex/capabilities/probe` returned `Codex ImageGen 探测超时。` with CLI `0.162.0-alpha.17.2`, `image_generation_advertised: true`, `e2e_verified: false`; no verified path was cached and no run/candidate was created. Sanitized response: [evidence JSON](../qa/evidence/codex-bundled-runtime-probe-2026-10-15.json). |
| Configured Cursor CLI API probe (2026-10-15, SQLite) | `unavailable` | `IP_STUDIO_CODEX_IMAGEGEN_EXECUTABLE` selected the independent `0.154.0-alpha.6.2` binary. The authenticated API returned exit code `1`; no native result passed validation, no path was cached, and no run/candidate was created. [Evidence JSON](../qa/evidence/codex-configured-runtime-probe-2026-10-15.json). |
| ChatGPT Web fallback | Always enabled | Existing manual task, prompt/reference ZIP, and browser upload path remain independent of the Codex probe |

The first CLI attempt was rejected because the temporary directory was outside a trusted Git
checkout. The retry used Codex's documented `--skip-git-repo-check` option, an ephemeral session,
and a temporary working directory. During that run, model discovery and the hosted tool connection
logged transient timeouts before the image was generated successfully. A timeout must therefore be
reported as an unavailable/failed probe for that attempt; the service must not fabricate an image
or silently switch to a developer API.

The API's `GET /api/v1/codex/capabilities` only reads CLI login and App Server provider capability;
it does not run inference. `POST /api/v1/codex/capabilities/probe` is the explicit, usage-consuming
probe. The API promotes the same CLI path and version to `available` only after its native
ImageGen event is present and its bounded PNG output passes the normal image decoder. Successful
probe output is temporary and is not imported as a project asset. A changed CLI path or version
invalidates the cached result.

The concluded PostgreSQL-backed API attempts confirm why the second gate exists: provider
advertisement alone is not enough. The CLI returned either no recognized native ImageGen event or
exit code `1`, and the API did not verify a PNG. The actual generation run was therefore not
started. A later isolated SQLite-backed request was interrupted before a report could be captured;
it is inconclusive. The desktop-bundled CLI also timed out through the same API-owned probe. Neither
result changes AC-25; keep ChatGPT Web manual generation available while no compatible runtime is
available.

## ChatGPT-plan compatibility finding (researched 2026-10-15)

OpenAI's [Sign in with ChatGPT preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
explicitly list Image Generation as unsupported for ChatGPT-plan use through the Responses API,
both directly and through Codex App Server. The same document says App Server sends inference over
HTTP/SSE to Responses and does not accept arbitrary Responses parameters. This rules out treating
that documented App Server/Responses route as a supported ImageGen runtime.

IP Studio's administrator probe invokes `codex exec`, not `codex app-server`, and captures neither
the effective transport nor stderr. The App Server limitation therefore does **not** prove why
these `codex exec` subprocesses time out or exit `1`; the verified fact is only that no API-owned
probe has produced both a successful native ImageGen event and a decodable PNG. Do not infer a
single root cause from the similar symptoms.

First-party Codex issue reports add evidence of a separate availability problem: [#37496](https://github.com/openai/codex/issues/37496)
reports ChatGPT-authenticated CLI sessions with the `image_generation` flag enabled but no tool
provisioned, and [#44039](https://github.com/openai/codex/issues/44039) reports the built-in tool
missing in both a fresh desktop task and a standalone CLI session. Both were still open when checked
on 2026-10-15; they are user reports, not maintainer-confirmed diagnoses or supported workarounds.

The first-party [ImageGen skill](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/imagegen/SKILL.md)
defines built-in `image_gen` as the default path and says its CLI fallback requires `OPENAI_API_KEY`.
That fallback is a separate developer API billing path and is excluded by this product's invariants.
The research found no documented way to make an external IP Studio process invoke the current
Codex task's session-injected `image_gen` tool, nor a supported CLI option that forces tool
provisioning. Keep AC-25 blocked until a real local runtime passes the existing API-owned gate;
ChatGPT Web manual generation/import remains the working fallback. Do not use private endpoints,
browser credentials, or a developer API key to bypass the gate.

IP Studio does not call ChatGPT private endpoints, read browser cookies, or use Plus as a developer
API key. App Server/CLI authentication stays inside the installed Codex runtime. PostgreSQL
availability is unrelated to this capability check.

## Alternate local runtime check (2026-10-15)

The host exposes four Codex executables: Homebrew stable `0.162.1`, the ChatGPT desktop-bundled
`0.162.0-alpha.17.2`, the Cursor extension-bundled `0.154.0-alpha.6.2`, and the wrapper that
resolves to the desktop-bundled binary. The distinct binaries authenticate as ChatGPT-plan users
and advertise ImageGen, but their API-owned probes did not pass (timeout or exit code `1`). The
desktop app itself is up to date. The [current
ChatGPT-plan compatibility limits](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
say Image Generation is unsupported through Codex App Server's Responses path. The open upstream
reports [#37496](https://github.com/openai/codex/issues/37496) and [#44039](https://github.com/openai/codex/issues/44039)
also describe ChatGPT-authenticated CLI/desktop sessions where the tool is not provisioned despite
the feature flag. These reports offer no supported fix. No installed, documented, policy-compliant
runtime on this host currently satisfies AC-25. A future runtime must pass the same API-owned native
event + PNG validation; do not switch to the paid Images/Responses API, private endpoints, or
browser credentials.

The API can select an operator-provided absolute CLI path using
`IP_STUDIO_CODEX_IMAGEGEN_EXECUTABLE`. An invalid configured path returns `unavailable` without
falling back to another executable found on `PATH`; a valid path is still gated by the real native
ImageGen event and decoded PNG checks.
