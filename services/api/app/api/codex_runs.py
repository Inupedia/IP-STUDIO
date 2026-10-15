from pathlib import Path
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.codex.capabilities import probe_capabilities
from app.codex.adapter import request_codex_cancellation
from app.db import get_session
from app.dependencies import get_current_admin
from app.models.codex_runs import CodexRun
from app.models.generation import GenerationTask
from app.models.story import Episode, Series
from app.models.workspace import User
from app.schemas.codex_runs import CodexRunRead
from app.services.codex_runs import run_codex_generation

router = APIRouter(prefix="/api/v1", tags=["codex-runs"])


def _read(run: CodexRun, panel_id: UUID) -> CodexRunRead:
    return CodexRunRead(
        run_id=run.id,
        task_id=run.task_id,
        panel_id=panel_id,
        status=run.status,
        candidate_id=run.candidate_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_reason=run.error_reason,
        created_at=run.created_at,
    )


def _get_run(
    session: Session, workspace_id: UUID, run_id: UUID, *, lock: bool = False
) -> tuple[CodexRun, UUID] | None:
    statement = (
        select(CodexRun, GenerationTask.panel_id)
        .join(
            GenerationTask,
            (GenerationTask.id == CodexRun.task_id)
            & (GenerationTask.workspace_id == CodexRun.workspace_id),
        )
        .where(CodexRun.id == run_id, CodexRun.workspace_id == workspace_id)
    )
    if lock:
        statement = statement.with_for_update()
    row = session.execute(statement).first()
    return (row[0], row[1]) if row else None


@router.post(
    "/generation-tasks/{task_id}/codex-runs",
    response_model=CodexRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_codex_run(
    task_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CodexRunRead:
    verified_path = request.app.state.codex_imagegen_verified_path
    verified_version = request.app.state.codex_imagegen_verified_version
    report = probe_capabilities(
        configured_codex_path=request.app.state.codex_imagegen_executable_path,
        e2e_verified=bool(verified_path and verified_version),
        verified_codex_path=verified_path,
        verified_codex_version=verified_version,
    )
    if (
        report.status != "available"
        or not report.e2e_verified
        or report.codex_path != verified_path
        or report.codex_version != verified_version
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="本机 Codex ImageGen 尚未通过当前版本的真实图片探测；可继续使用 ChatGPT 网页手动生成。",
        )

    task = session.scalar(
        select(GenerationTask)
        .where(
            GenerationTask.id == task_id,
            GenerationTask.workspace_id == current_admin.workspace_id,
        )
        .with_for_update()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation task not found")
    if task.status not in {"prepared", "asset_imported"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only prepared tasks can start local Codex ImageGen; use the manual ChatGPT flow otherwise.",
        )
    active_run = session.scalar(
        select(CodexRun.id).where(
            CodexRun.task_id == task.id,
            CodexRun.workspace_id == current_admin.workspace_id,
            CodexRun.status.in_(["queued", "running"]),
        )
    )
    if active_run is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Codex run is already active")

    run = CodexRun(
        workspace_id=current_admin.workspace_id,
        task_id=task.id,
        status="queued",
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A Codex run is already active") from error
    session.refresh(run)
    background_tasks.add_task(
        run_codex_generation,
        request.app.state.session_factory,
        run.id,
        verified_path,
        Path(request.app.state.asset_storage_dir),
        Path(request.app.state.codex_job_root),
        request.app.state.asset_max_bytes,
        request.app.state.asset_max_pixels,
    )
    return _read(run, task.panel_id)


@router.get("/codex-runs/{run_id}", response_model=CodexRunRead)
def read_codex_run(
    run_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CodexRunRead:
    row = _get_run(session, current_admin.workspace_id, run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Codex run not found")
    return _read(*row)


@router.post("/codex-runs/{run_id}/cancel", response_model=CodexRunRead)
def cancel_codex_run(
    run_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CodexRunRead:
    row = _get_run(session, current_admin.workspace_id, run_id, lock=True)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Codex run not found")
    run, panel_id = row
    if run.status not in {"queued", "running"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Codex run is already finished")
    if run.status == "running":
        request_codex_cancellation(str(run.id))
    if run.started_at is None:
        run.started_at = datetime.now(timezone.utc)
    run.status = "failed"
    run.completed_at = datetime.now(timezone.utc)
    run.error_reason = "已由管理员取消。"
    session.commit()
    session.refresh(run)
    return _read(run, panel_id)
