from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ip import IP
from app.models.story import Episode, Series
from app.models.workspace import Workspace


class ResourceNotFound(Exception):
    pass


class ResourceConflict(Exception):
    pass


def list_ips(session: Session, workspace_id: UUID) -> list[IP]:
    return list(
        session.scalars(
            select(IP)
            .where(IP.workspace_id == workspace_id)
            .order_by(IP.created_at, IP.id)
        )
    )


def get_ip(session: Session, workspace_id: UUID, ip_id: UUID) -> IP:
    ip = session.scalar(select(IP).where(IP.id == ip_id, IP.workspace_id == workspace_id))
    if ip is None:
        raise ResourceNotFound("IP not found")
    return ip


def create_ip(
    session: Session,
    workspace_id: UUID,
    code: str,
    name: str,
    summary: str | None = None,
) -> IP:
    if session.get(Workspace, workspace_id) is None:
        raise ResourceNotFound("Workspace not found")
    ip = IP(workspace_id=workspace_id, code=code.strip().upper(), name=name.strip(), summary=summary)
    session.add(ip)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("An IP with this code already exists in the workspace") from error
    session.refresh(ip)
    return ip


def list_series(session: Session, workspace_id: UUID, ip_id: UUID | None = None) -> list[Series]:
    query = select(Series).where(Series.workspace_id == workspace_id)
    if ip_id is not None:
        get_ip(session, workspace_id, ip_id)
        query = query.where(Series.ip_id == ip_id)
    return list(session.scalars(query.order_by(Series.created_at, Series.id)))


def get_series(session: Session, workspace_id: UUID, series_id: UUID) -> Series:
    series = session.scalar(
        select(Series).where(Series.id == series_id, Series.workspace_id == workspace_id)
    )
    if series is None:
        raise ResourceNotFound("Series not found")
    return series


def create_series(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    name: str,
    summary: str | None = None,
) -> Series:
    get_ip(session, workspace_id, ip_id)
    series = Series(workspace_id=workspace_id, ip_id=ip_id, name=name.strip(), summary=summary)
    session.add(series)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("Series could not be created") from error
    session.refresh(series)
    return series


def list_episodes(session: Session, workspace_id: UUID, series_id: UUID) -> list[Episode]:
    get_series(session, workspace_id, series_id)
    return list(
        session.scalars(
            select(Episode)
            .where(Episode.series_id == series_id, Episode.workspace_id == workspace_id)
            .order_by(Episode.number)
        )
    )


def create_episode(
    session: Session,
    workspace_id: UUID,
    series_id: UUID,
    number: int,
    title: str,
) -> Episode:
    get_series(session, workspace_id, series_id)
    episode = Episode(
        workspace_id=workspace_id,
        series_id=series_id,
        number=number,
        title=title.strip(),
    )
    session.add(episode)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ResourceConflict("This episode number already exists in the series") from error
    session.refresh(episode)
    return episode
