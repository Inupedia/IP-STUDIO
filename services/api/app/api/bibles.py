from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies import get_current_admin
from app.models.bibles import Character, CharacterVersion, Style, StyleVersion
from app.models.workspace import User
from app.schemas.bibles import (
    CharacterCreate,
    CharacterRead,
    CharacterVersionCandidate,
    CharacterVersionRead,
    DefaultStyleRead,
    DefaultStyleUpdate,
    StyleCreate,
    StyleRead,
    StyleVersionCandidate,
    StyleVersionRead,
)
from app.services.bibles import (
    ResourceConflict,
    ResourceNotFound,
    approve_character_version,
    approve_style_version,
    create_character_candidate,
    create_character_version_candidate,
    create_style_candidate,
    create_style_version_candidate,
    get_character_version,
    get_style_version,
    list_characters,
    list_styles,
    set_default_style,
)

router = APIRouter(prefix="/api/v1", tags=["bibles"])


def _character_version_read(version: CharacterVersion) -> CharacterVersionRead:
    return CharacterVersionRead(
        character_version_id=version.id,
        character_id=version.character_id,
        version_no=version.version_no,
        status=version.status,
        bible=version.bible_json,
        derived_from_version_id=version.derived_from_version_id,
        approved_at=version.approved_at,
    )


def _style_version_read(version: StyleVersion) -> StyleVersionRead:
    return StyleVersionRead(
        style_version_id=version.id,
        style_id=version.style_id,
        version_no=version.version_no,
        status=version.status,
        bible=version.bible_json,
        derived_from_version_id=version.derived_from_version_id,
        approved_at=version.approved_at,
    )


def _character_read(
    character: Character, versions: list[CharacterVersion]
) -> CharacterRead:
    return CharacterRead(
        character_id=character.id,
        ip_id=character.ip_id,
        code=character.code,
        name=character.name,
        versions=[_character_version_read(version) for version in versions],
    )


def _style_read(style: Style, versions: list[StyleVersion]) -> StyleRead:
    return StyleRead(
        style_id=style.id,
        ip_id=style.ip_id,
        name=style.name,
        versions=[_style_version_read(version) for version in versions],
    )


def _raise_bible_error(error: ResourceNotFound | ResourceConflict) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if isinstance(error, ResourceNotFound) else status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


@router.get("/ips/{ip_id}/characters", response_model=list[CharacterRead])
def read_characters(
    ip_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[CharacterRead]:
    try:
        return [
            _character_read(character, versions)
            for character, versions in list_characters(session, current_admin.workspace_id, ip_id)
        ]
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.post(
    "/ips/{ip_id}/characters",
    response_model=CharacterVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_character(
    ip_id: UUID,
    payload: CharacterCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CharacterVersionRead:
    try:
        _, version = create_character_candidate(
            session,
            current_admin.workspace_id,
            ip_id,
            payload.code,
            payload.name,
            payload.bible.model_dump(mode="json", exclude_unset=True),
        )
        return _character_version_read(version)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.post(
    "/characters/{character_id}/versions",
    response_model=CharacterVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_character_version(
    character_id: UUID,
    payload: CharacterVersionCandidate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CharacterVersionRead:
    try:
        version = create_character_version_candidate(
            session,
            current_admin.workspace_id,
            character_id,
            payload.base_version_id,
            payload.bible.model_dump(mode="json", exclude_unset=True),
        )
        return _character_version_read(version)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.get("/character-versions/{version_id}", response_model=CharacterVersionRead)
def read_character_version(
    version_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CharacterVersionRead:
    try:
        return _character_version_read(
            get_character_version(session, current_admin.workspace_id, version_id)
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.post("/character-versions/{version_id}/approve", response_model=CharacterVersionRead)
def approve_character(
    version_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> CharacterVersionRead:
    try:
        return _character_version_read(
            approve_character_version(
                session, current_admin.workspace_id, version_id, current_admin.id
            )
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.get("/ips/{ip_id}/styles", response_model=list[StyleRead])
def read_styles(
    ip_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> list[StyleRead]:
    try:
        return [
            _style_read(style, versions)
            for style, versions in list_styles(session, current_admin.workspace_id, ip_id)
        ]
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.post(
    "/ips/{ip_id}/styles",
    response_model=StyleVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_style(
    ip_id: UUID,
    payload: StyleCreate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> StyleVersionRead:
    try:
        _, version = create_style_candidate(
            session,
            current_admin.workspace_id,
            ip_id,
            payload.name,
            payload.bible.model_dump(mode="json", exclude_unset=True),
        )
        return _style_version_read(version)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.post(
    "/styles/{style_id}/versions",
    response_model=StyleVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_style_version(
    style_id: UUID,
    payload: StyleVersionCandidate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> StyleVersionRead:
    try:
        version = create_style_version_candidate(
            session,
            current_admin.workspace_id,
            style_id,
            payload.base_version_id,
            payload.bible.model_dump(mode="json", exclude_unset=True),
        )
        return _style_version_read(version)
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.get("/style-versions/{version_id}", response_model=StyleVersionRead)
def read_style_version(
    version_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> StyleVersionRead:
    try:
        return _style_version_read(get_style_version(session, current_admin.workspace_id, version_id))
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.post("/style-versions/{version_id}/approve", response_model=StyleVersionRead)
def approve_style(
    version_id: UUID,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> StyleVersionRead:
    try:
        return _style_version_read(
            approve_style_version(session, current_admin.workspace_id, version_id, current_admin.id)
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error


@router.put("/ips/{ip_id}/default-style", response_model=DefaultStyleRead)
def update_default_style(
    ip_id: UUID,
    payload: DefaultStyleUpdate,
    current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_session)],
) -> DefaultStyleRead:
    try:
        ip = set_default_style(
            session, current_admin.workspace_id, ip_id, payload.style_version_id
        )
        return DefaultStyleRead(
            ip_id=ip.id,
            default_style_version_id=ip.default_style_version_id,
        )
    except (ResourceNotFound, ResourceConflict) as error:
        raise _raise_bible_error(error) from error
