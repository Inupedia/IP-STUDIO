from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_admin
from app.models.workspace import User
from app.codex.capabilities import (
    CapabilityReport,
    probe_capabilities,
    run_image_generation_probe,
)

router = APIRouter(prefix="/api/v1/codex", tags=["codex"])


@router.get("/capabilities", response_model=CapabilityReport)
def read_capabilities(
    request: Request,
    _current_admin: Annotated[User, Depends(get_current_admin)],
) -> CapabilityReport:
    codex_path = request.app.state.codex_imagegen_verified_path
    codex_version = request.app.state.codex_imagegen_verified_version
    verified = bool(codex_path and codex_version)
    return probe_capabilities(
        e2e_verified=verified,
        verified_codex_path=codex_path,
        verified_codex_version=codex_version,
    )


@router.post("/capabilities/probe", response_model=CapabilityReport)
def run_capability_probe(
    request: Request,
    _current_admin: Annotated[User, Depends(get_current_admin)],
) -> CapabilityReport:
    report = probe_capabilities()
    if not report.codex_path or not report.image_generation_advertised:
        request.app.state.codex_imagegen_verified_path = None
        request.app.state.codex_imagegen_verified_version = None
        return report

    result = run_image_generation_probe(report.codex_path)
    if not result.verified or result.image is None:
        request.app.state.codex_imagegen_verified_path = None
        request.app.state.codex_imagegen_verified_version = None
        return report.model_copy(update={"reason": result.reason, "e2e_verified": False})

    request.app.state.codex_imagegen_verified_path = report.codex_path
    request.app.state.codex_imagegen_verified_version = report.codex_version
    return probe_capabilities(
        e2e_verified=True,
        verified_codex_path=report.codex_path,
        verified_codex_version=report.codex_version,
    )
