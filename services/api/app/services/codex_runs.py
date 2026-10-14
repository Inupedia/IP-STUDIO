from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.codex.adapter import CodexRunCancelled, clear_codex_cancellation, generate_image
from app.codex.image_result import ImageResultError
from app.models.generation import GenerationTask
from app.models.codex_runs import CodexRun
from app.models.story import Episode, Series
from app.services.assets import upload_asset
from app.services.candidate_assets import import_candidate
from app.services.reference_bundle import create_reference_bundle


def _failed(session_factory: sessionmaker[Session], run_id: UUID, reason: str) -> None:
    with session_factory() as session:
        run = session.get(CodexRun, run_id)
        if run is None or run.status not in {"queued", "running"}:
            return
        if run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_reason = reason[:500]
        session.commit()


def run_codex_generation(
    session_factory: sessionmaker[Session],
    run_id: UUID,
    codex_path: str,
    storage_dir: Path,
    job_root: Path,
    max_bytes: int,
    max_pixels: int,
) -> None:
    prompt: str | None = None
    bundle: bytes | None = None
    workspace_id: UUID | None = None
    task_id: UUID | None = None
    panel_id: UUID | None = None
    ip_id: UUID | None = None

    try:
        with session_factory() as session:
            run = session.scalar(
                select(CodexRun).where(CodexRun.id == run_id).with_for_update()
            )
            if run is None or run.status != "queued":
                return
            task = session.scalar(
                select(GenerationTask).where(
                    GenerationTask.id == run.task_id,
                    GenerationTask.workspace_id == run.workspace_id,
                )
            )
            if task is None:
                raise RuntimeError("Generation task no longer exists")
            if task.status not in {"prepared", "asset_imported"}:
                raise RuntimeError("Generation task is no longer eligible for Codex ImageGen")
            episode_ip = session.execute(
                select(Series.ip_id)
                .join(Episode, Episode.series_id == Series.id)
                .where(Episode.id == task.episode_id, Episode.workspace_id == run.workspace_id)
            ).scalar_one_or_none()
            if episode_ip is None:
                raise RuntimeError("Generation task episode no longer exists")

            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            session.commit()

            workspace_id = run.workspace_id
            task_id = task.id
            panel_id = task.panel_id
            ip_id = episode_ip
            prompt_value: Any = task.prompt_snapshot.get("text")
            if not isinstance(prompt_value, str) or not prompt_value.strip():
                raise RuntimeError("Generation task has no frozen prompt")
            prompt = prompt_value
            bundle = create_reference_bundle(session, run.workspace_id, task.id, storage_dir)

        job_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix=f"run-{run_id}-", dir=job_root) as raw_job_dir:
            job_dir = Path(raw_job_dir)
            try:
                generated = generate_image(codex_path, prompt, bundle, job_dir)
            except CodexRunCancelled:
                return
            except ImageResultError as error:
                raise RuntimeError(str(error)) from error
            data = generated.path.read_bytes()

            with session_factory() as session:
                run = session.scalar(
                    select(CodexRun).where(CodexRun.id == run_id).with_for_update()
                )
                if run is None or run.status != "running":
                    return
                assert workspace_id is not None and task_id is not None and ip_id is not None
                record = upload_asset(
                    session,
                    workspace_id,
                    ip_id,
                    f"Panel {str(panel_id)[:8]} — Codex ImageGen",
                    "composite_panel",
                    "Local Codex ImageGen output; human approval required.",
                    "codex-imagegen.png",
                    data,
                    generated.image.mime,
                    storage_dir,
                    max_bytes,
                    max_pixels,
                    source_type="codex_native",
                    commit=False,
                )
                candidate = import_candidate(
                    session,
                    workspace_id,
                    task_id,
                    record.version.id,
                    allow_prepared=True,
                    commit=False,
                )
                session.flush()
                run.status = "candidate_ready"
                run.candidate_id = candidate.id
                run.completed_at = datetime.now(timezone.utc)
                run.error_reason = None
                session.commit()
    except Exception as error:
        if isinstance(error, (ImageResultError, RuntimeError)):
            safe_reason = str(error)
        else:
            safe_reason = "Codex generation failed before an asset candidate could be created."
        _failed(session_factory, run_id, safe_reason)
    finally:
        clear_codex_cancellation(str(run_id))
