# Codex ImageGen capability matrix

Last checked: 2026-10-14 (Asia/Shanghai)

This is environment evidence, not a product-wide guarantee. IP Studio must repeat the read-only
runtime checks for its own process and requires an explicit administrator E2E probe before its API
reports `available`.

| Probe | Result | Evidence |
|---|---|---|
| Codex CLI installed | Yes | `/opt/homebrew/bin/codex`, `codex-cli 0.162.1` |
| Codex login | Yes | `codex login status` reported `Logged in using ChatGPT`; no token or cookie was read by IP Studio |
| Local App Server | Yes | `codex app-server --listen stdio://` initialized and answered `modelProvider/capabilities/read` |
| Provider advertises ImageGen | Yes | App Server reported `imageGeneration: true` |
| Real native ImageGen output | Yes, for this local Codex session | An explicit `codex exec` call invoked native ImageGen, saved a PNG in the Codex-generated output directory, and copied it to `/tmp/ip-studio-imagegen-probe/probe.png` |
| PNG integrity | Passed | `file` identified PNG; Pillow `Image.verify()` and a full decode succeeded; 1254×1254 RGB, 1,627,707 bytes |
| IP Studio API-owned administrator probe (2026-10-14, PostgreSQL) | `unavailable` | Authenticated FastAPI requests confirmed `imageGeneration: true`, but the CLI did not record a successful native ImageGen event or bounded PNG; one retry exited `1`. The API correctly refused to mark the capability available, so no native run or candidate was created. |
| Follow-up isolated API probe (2026-10-14, SQLite) | Inconclusive | The authenticated request did not return a report and was manually interrupted. Its temporary directory was cleaned up; no event log or PNG was retained for verification. This attempt changes neither the earlier API result nor AC-25. |
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
it is inconclusive and does not change AC-25. Retry only after the local Codex ImageGen runtime is
healthy; keep ChatGPT Web manual generation available while it is not.

## ChatGPT-plan compatibility finding (2026-10-14)

OpenAI's [Sign in with ChatGPT preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
state that Image Generation is unsupported for ChatGPT-plan usage through the Responses API,
including requests made through Codex App Server. This is consistent with the API-owned probe
failing under the current local ChatGPT login, but it is an inference rather than a confirmed
diagnosis: IP Studio does not inspect credentials or expose the effective provider transport, and
the CLI probe intentionally discards stderr. The current verified fact remains that this API-owned
CLI path did not produce a native ImageGen event plus a decodable PNG. Do not clear AC-25 by retrying
or by using a private endpoint, browser cookie, or developer API credential; a supported local
runtime must pass the same end-to-end gate, or the product requirement must be revised through the
design workflow.

IP Studio does not call ChatGPT private endpoints, read browser cookies, or use Plus as a developer
API key. App Server/CLI authentication stays inside the installed Codex runtime. PostgreSQL
availability is unrelated to this capability check.
