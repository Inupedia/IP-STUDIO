# PostgreSQL 与图片 Blob 备份/恢复

恢复会替换目标数据库和 Blob 目录。先核验备份文件、确认目标环境，并停止 API 写入。不要把 SQL dump 与不同时间的图片目录混在一起。

## 备份

1. 安排维护窗口，停止 API/Web 写入；待上传和导出请求结束。
2. 在仓库根目录执行：

```bash
backup_dir="backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
docker compose exec -T database pg_dump -U ip_studio -d ip_studio -Fc > "$backup_dir/ip-studio.dump"
tar -C var -czf "$backup_dir/blobs.tar.gz" blobs
(
  cd "$backup_dir"
  shasum -a 256 ip-studio.dump blobs.tar.gz > SHA256SUMS
)
```

数据库名与用户需和 `.env` / Compose 一致；若修改过默认值，同步调整 `pg_dump` 参数。把整个时间戳目录复制到另一块加密存储，且与生产主机分离。备份包含用户资产，按其敏感度设访问控制和保留期限。

## 恢复到现有开发实例

1. 先停止 API，避免恢复期间继续写入。本地开发指南通过终端 B 单独运行 `uvicorn`；在该终端按 `Ctrl+C`，等日志显示服务关闭并返回 shell 提示符。若目标环境由容器或平台服务托管，先按该环境的方式停止 API，并确认服务已退出。

```bash
if curl --connect-timeout 2 --silent --fail http://127.0.0.1:8000/api/v1/health >/dev/null; then
  echo "API 仍在运行；停止 API 后再恢复。" >&2
  exit 1
fi
docker compose stop database
```

2. 在仓库根目录核对备份，并解压到暂存目录：

```bash
cd backups/<UTC 时间戳目录>
shasum -a 256 -c SHA256SUMS
mkdir -p ../../var/restore-stage
tar -xzf blobs.tar.gz -C ../../var/restore-stage
```

确认暂存路径存在 `../../var/restore-stage/blobs` 后，启动数据库，并**替换**目标库：

```bash
cd ../..
docker compose up -d database
docker compose exec -T database dropdb -U ip_studio --if-exists ip_studio
docker compose exec -T database createdb -U ip_studio ip_studio
docker compose exec -T database pg_restore -U ip_studio -d ip_studio --no-owner --exit-on-error < "backups/<UTC 时间戳目录>/ip-studio.dump"
mv var/blobs "var/blobs.before-restore-$(date -u +%Y%m%dT%H%M%SZ)"
mv var/restore-stage/blobs var/blobs
```

这些命令会清空并重建当前 `ip_studio` 数据库，并将当前 Blob 目录移到带时间戳的回滚目录；它们不会合并数据。确认 dump 可读、存储空间足够且目标实例正确后再执行。

3. 在终端 B 启动 API：

```bash
uv run --project services/api uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --reload
```

等待服务启动后，在仓库根目录验证：

```bash
uv run --project services/api alembic -c services/api/alembic.ini current
curl --fail http://127.0.0.1:8000/api/v1/health
```

登录 UI，打开含图片的旧单集，检查素材预览，再导出工程 ZIP 并核对 manifest/hash。验证通过后可删除临时恢复目录和旧数据副本；未通过时停止 API，保留两份 Blob 目录与 dump 以便回滚。

## 发布演练记录

### Completed test run — 2026-10-14

- PostgreSQL `17.11`（本机 Compose/OrbStack）；Alembic `upgrade head`、`check`、`downgrade base`、`upgrade head`、`check` 全部通过。
- 通过真实 API 建立临时管理员、IP、Series、Episode、已批准模板、图片 Blob 和文档；使用 PostgreSQL custom dump 与 Blob tar 分别备份。
- 在临时开发数据库上执行 `dropdb` / `createdb` / `pg_restore`，再恢复 Blob 目录；验证管理员重新登录、图片内容与恢复前逐字节一致、工程 ZIP 可重新导出且含 manifest、文档和 content-addressed 图片。
- 演练结束后清空该测试 workspace，将数据库恢复为空的 Alembic head，并停止 Compose 数据库容器。备份文件和临时 Blob 留在临时目录，已在演练后清理；未覆盖真实用户数据。

AC-18 的本地联合恢复验收已通过。部署到新环境或升级存储方式时，仍应重新执行本 Runbook，并在 [V1-release-checklist.md](../qa/V1-release-checklist.md) 记录运行环境和结果。
