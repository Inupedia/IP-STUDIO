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
| IP Studio API-owned administrator probe (2026-10-14, PostgreSQL) | `unavailable` (historical) | The first implementation required an ImageGen event in `codex exec --json`, which CLI `0.162.1` omitted; an earlier retry exited `1`. The probe correctly refused to mark the capability available. Superseded by the successful App Server history readback below. |
| Follow-up isolated API probe (2026-10-14, SQLite) | Inconclusive | The authenticated request did not return a report and was manually interrupted. Its temporary directory was cleaned up; no event log or PNG was retained for verification. This attempt changes neither the earlier API result nor AC-25. |
| Desktop-bundled CLI API probe (2026-10-15, SQLite) | `unavailable` | The authenticated `POST /api/v1/codex/capabilities/probe` returned `Codex ImageGen 探测超时。` with CLI `0.162.0-alpha.17.2`, `image_generation_advertised: true`, `e2e_verified: false`; no verified path was cached and no run/candidate was created. Sanitized response: [evidence JSON](../qa/evidence/codex-bundled-runtime-probe-2026-10-15.json). |
| Configured Cursor CLI API probe (2026-10-15, SQLite) | `unavailable` | `IP_STUDIO_CODEX_IMAGEGEN_EXECUTABLE` selected the independent `0.154.0-alpha.6.2` binary. The authenticated API returned exit code `1`; no native result passed validation, no path was cached, and no run/candidate was created. [Evidence JSON](../qa/evidence/codex-configured-runtime-probe-2026-10-15.json). |
| Explicit model + feature CLI probe (2026-10-15, standalone) | PNG decoded; JSONL item absent | Homebrew CLI `0.162.1`, `--model gpt-6.1-sol --enable image_generation`, exited `0` and wrote a decodable 1254×1254 PNG. The standalone run is not API-owned and does not satisfy AC-25. [Evidence JSON](../qa/evidence/codex-explicit-model-runtime-probe-2026-10-15.json). |
| App Server persisted-history readback (2026-10-15) | Passed | A persistent `codex exec --json` run produced a thread ID. The local public `thread/read` API returned `type=imageGeneration`, `status=completed`, and `savedPath` for that exact thread. The CLI JSONL serializer omitted the item, while App Server history retained it. A disposable session was then deleted through public `thread/delete`. |
| API-owned administrator probe and candidate round trip (2026-10-15, SQLite) | Passed | Authenticated FastAPI `POST /api/v1/codex/capabilities/probe` with the Homebrew CLI returned `available` and `e2e_verified=true`; the saved native PNG matched the bounded probe output byte for byte and decoded. In the same API instance, a real Codex run created a `codex_native` candidate in `pending_review`; admin approval changed it to `approved`. The temporary DB/Blob store was discarded. [Sanitized evidence](../qa/evidence/ac25-native-imagegen-app-server-readback-2026-10-15.json). |
| ChatGPT Web fallback | Always enabled | Existing manual task, prompt/reference ZIP, and browser upload path remain independent of the Codex probe |

The first CLI attempt was rejected because the temporary directory was outside a trusted Git
checkout. The retry used Codex's documented `--skip-git-repo-check` option, an ephemeral session,
and a temporary working directory. During that run, model discovery and the hosted tool connection
logged transient timeouts before the image was generated successfully. A timeout must therefore be
reported as an unavailable/failed probe for that attempt; the service must not fabricate an image
or silently switch to a developer API.

The API's `GET /api/v1/codex/capabilities` only reads CLI login and App Server provider capability;
it does not run inference. `POST /api/v1/codex/capabilities/probe` is the explicit, usage-consuming
probe. `codex exec --json` starts a persistent thread so the API can capture its `thread.started`
ID, then asks the same local App Server to `thread/read` that thread. It requires a completed
`imageGeneration` item, a PNG `savedPath` under that thread's Codex-owned generated-images folder,
and byte-for-byte equality with the bounded PNG in the IP Studio job directory before decoding.
The test thread and its Codex-generated image are removed after verification; probe output is not
imported as a project asset. A changed CLI path or version invalidates the cached result.

The earlier PostgreSQL-backed attempts exposed a mismatch between `codex exec --json` and persisted
Codex history: CLI `0.162.1` did not serialize the native ImageGen item into JSONL. The first API
implementation treated that missing JSONL item as no native event. The standalone run itself had
successfully generated a PNG, but that alone was insufficient evidence. Reading the same persistent
thread through the public local App Server protocol resolved the mismatch; the API now verifies the
native item and its saved PNG in one run. The desktop-bundled and Cursor-bundled CLIs remain
unavailable in this host; the Homebrew runtime passed the API-owned probe and candidate round trip.

## ChatGPT-plan compatibility finding (researched 2026-10-15)

OpenAI's [Sign in with ChatGPT preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
explicitly list Image Generation as unsupported for ChatGPT-plan inference through the Responses
API, including inference initiated through Codex App Server. IP Studio does not use App Server for
generation: it asks the local Codex CLI to run the native tool, then uses App Server's public,
read-only `thread/read` method to inspect that CLI session's persisted history. The history protocol
includes `ThreadItem::ImageGeneration` and exposes its completion status and saved path. This does
not route ImageGen through the unsupported App Server/Responses inference path.

The mismatch is present in the version-pinned source: CLI JSONL maps a limited `ThreadItemDetails`
set and drops unrecognized thread items, while core persisted history contains an
`ImageGeneration` variant and App Server registers `thread/read`. See the [CLI JSONL mapper](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/exec/src/event_processor_with_jsonl_output.rs),
[persisted item types](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/protocol/src/items.rs),
and [App Server protocol registry](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/app-server-protocol/src/protocol/common.rs).

The earlier `codex exec --json` attempts time out or exit `1` for some bundled runtimes; the
App Server inference limitation does **not** explain those failures. The Homebrew CLI `0.162.1`
currently passed the API-owned probe after the API read back the native item from persisted history.
Do not treat the unsupported inference path as a blanket limitation on App Server's read-only
thread-history protocol.

First-party Codex issue reports add evidence of a separate availability problem: [#37496](https://github.com/openai/codex/issues/37496)
reports ChatGPT-authenticated CLI sessions with the `image_generation` flag enabled but no tool
provisioned, and [#44039](https://github.com/openai/codex/issues/44039) reports the built-in tool
missing in both a fresh desktop task and a standalone CLI session. Both were still open when checked
on 2026-10-15; they are user reports, not maintainer-confirmed diagnoses or supported workarounds.

The first-party [ImageGen skill](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/imagegen/SKILL.md)
defines built-in `image_gen` as the default path and says its CLI fallback requires `OPENAI_API_KEY`.
That fallback is a separate developer API billing path and is excluded by this product's invariants.
This host's API uses the local CLI's native tool and public session-history protocol; it does not
invoke a different task's injected tool. ChatGPT Web manual generation/import remains available as
the fallback. Do not use private endpoints, browser credentials, or a developer API key to bypass
the gate.

IP Studio does not call ChatGPT private endpoints, read browser cookies, or use Plus as a developer
API key. App Server/CLI authentication stays inside the installed Codex runtime. PostgreSQL
availability is unrelated to this capability check.

## Alternate local runtime check (2026-10-15)

The host exposes Homebrew stable `0.162.1`, the ChatGPT desktop-bundled `0.162.0-alpha.17.2`, and
the Cursor extension-bundled `0.154.0-alpha.6.2`. All advertise ImageGen; only the Homebrew CLI
passed the API-owned probe and candidate round trip after the service switched native-event
verification to public App Server persisted-history readback. The desktop-bundled runtime timed
out and the Cursor runtime exited `1`; neither was cached as available. The desktop app itself is
up to date. The [current
ChatGPT-plan compatibility limits](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
say Image Generation is unsupported through Codex App Server's Responses path. The open upstream
reports [#37496](https://github.com/openai/codex/issues/37496) and [#44039](https://github.com/openai/codex/issues/44039)
also describe ChatGPT-authenticated CLI/desktop sessions where the tool is not provisioned despite
the feature flag; those reports did not match this successful local CLI session. These reports
offer no general workaround. Do not switch to the paid Images/Responses API, private endpoints, or
browser credentials.

The API can select an operator-provided absolute CLI path using
`IP_STUDIO_CODEX_IMAGEGEN_EXECUTABLE`. An invalid configured path returns `unavailable` without
falling back to another executable found on `PATH`; a valid path is still gated by a completed
native App Server history item, a matching saved PNG, and full image decoding.
