# 本地开发与启动

## 依赖

- Node.js `22.12+`、pnpm `10.33.2`
- Python `3.12+`、[uv](https://docs.astral.sh/uv/)
- Docker Compose v2

## 安装与配置

在仓库根目录执行：

```bash
pnpm install --frozen-lockfile
uv sync --project services/api --locked --group dev
cp .env.example .env
```

编辑根目录 `.env`：

- `JWT_SECRET_KEY` 至少 32 个随机字节。可用 `openssl rand -hex 32` 生成后粘贴到文件中。
- `.env.example` 的数据库账号和密码只供本机开发使用；线上请改为专用随机凭据，不要提交 `.env`。
- `ASSET_STORAGE_DIR=./var/blobs` 是相对仓库根目录的图片 Blob 目录。

## 启动服务

终端 A 启动 PostgreSQL：

```bash
docker compose up -d database
docker compose ps
```

终端 B 在仓库根目录迁移数据库、创建管理员并启动 API：

```bash
uv run --project services/api alembic -c services/api/alembic.ini upgrade head
uv run --project services/api python -m app.bootstrap
uv run --project services/api uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --reload
```

`bootstrap` 会交互式要求管理员邮箱与至少 12 字符密码。健康检查地址为 `http://127.0.0.1:8000/api/v1/health`。

终端 C 启动 Web：

```bash
pnpm --filter @ip-studio/web dev --host 127.0.0.1
```

默认 Web 地址为 `http://127.0.0.1:5173`，API 地址默认 `http://localhost:8000`。如 API 端口不同，可设置 `VITE_API_BASE_URL` 后重启 Vite。

## 开发验证

```bash
pnpm --filter @ip-studio/web test
pnpm --filter @ip-studio/web test:e2e
pnpm --filter @ip-studio/web build
uv run --project services/api pytest -q
```

CI 的浏览器任务会安装 Playwright Chromium；首次本地运行 E2E 可执行：

```bash
pnpm --filter @ip-studio/web exec playwright install chromium
```

所有 E2E API 数据来自固定 fixture 和浏览器 route mock。真实数据库迁移在 CI Postgres 服务运行；本机数据库备份与恢复按 [backup-restore.md](backup-restore.md) 操作。

## 停止

按 `Ctrl+C` 停止 API 与 Vite。PostgreSQL 数据保存在 Compose volume；`docker compose down` 会停止并移除容器，但保留 named volume。不要用 `docker compose down -v`，除非明确要删除所有本地数据库数据。
