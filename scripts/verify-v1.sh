#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

run_step() {
  local label="$1"
  shift
  printf '\n== %s ==\n' "$label"
  "$@"
}

run_step "Backend pytest" uv run --project services/api pytest -q
run_step "Frontend Vitest" pnpm --filter @ip-studio/web test
run_step "Playwright Chromium E2E" pnpm --filter @ip-studio/web test:e2e
run_step "Frontend production build" pnpm --filter @ip-studio/web build
