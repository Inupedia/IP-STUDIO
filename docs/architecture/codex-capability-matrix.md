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
| IP Studio API-owned administrator probe (2026-10-14) | `unavailable` | An authenticated FastAPI request confirmed `imageGeneration: true`, but the CLI probe did not record a successful native ImageGen event or a bounded PNG; a later retry exited `1`. The API correctly refused to mark the capability available, so no native run or candidate was created. |
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

The latest API-owned attempt confirms why the second gate exists: provider advertisement alone is
not enough. The CLI returned either no recognized native ImageGen event or exit code `1`, and did
not leave a PNG in the bounded probe directory. The actual generation run was therefore not
started. Retry only after the local Codex ImageGen runtime is healthy; keep ChatGPT Web manual
generation available while it is not.

IP Studio does not call ChatGPT private endpoints, read browser cookies, or use Plus as a developer
API key. App Server/CLI authentication stays inside the installed Codex runtime. PostgreSQL
availability is unrelated to this capability check.
