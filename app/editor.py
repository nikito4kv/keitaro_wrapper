"""Редактор офферов в потоках существующей кампании.

Как это работает:

1. При открытии кампании редактор сверяется с Keitaro и запоминает состав каждого потока.
2. «Добавить», «Убрать» и «Вернуть» меняют только черновик в нашей базе и пересчитывают доли.
   В Keitaro в этот момент ничего не уходит.
3. «Отправить в Keitaro» одним запросом заменяет состав офферов потока на черновик.
   «Отменить» возвращает черновик к тому, что сейчас в Keitaro.

Убранный оффер из Keitaro действительно удаляется, но остаётся в редакторе с пометкой
«убран», чтобы его можно было вернуть одной кнопкой.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.keitaro import KeitaroClient, KeitaroError
from app.models import StreamOffer
from app.schemas import (
    EditorOut,
    EditorStream,
    StreamFilterOut,
    StreamOfferOut,
    StreamOffersOut,
    TrackerCampaign,
)
from app.services import ServiceError
from app.shares import rebalance

OFFERS_SCHEMA = "landings"  # так Keitaro называет поток, который раздаёт офферы
REDIRECT_SCHEMA = "redirect"


# Чтение из Keitaro ------------------------------------------------------------


def campaign_summary(keitaro: KeitaroClient, campaign: dict[str, Any]) -> TrackerCampaign:
    campaign_id = int(campaign["id"])
    domain = str(campaign.get("domain") or "").strip().rstrip("/")
    alias = campaign.get("alias")
    return TrackerCampaign(
        id=campaign_id,
        name=str(campaign.get("name") or f"Кампания {campaign_id}"),
        state=str(campaign.get("state") or "active"),
        created_at=campaign.get("created_at"),
        url=f"{domain}/{alias}" if domain and alias else None,
        admin_url=keitaro.campaign_admin_url(campaign_id),
    )


def list_campaigns(keitaro: KeitaroClient, offset: int, limit: int) -> tuple[list[TrackerCampaign], bool]:
    # Просим на одну больше, чтобы понять, есть ли следующая страница.
    campaigns = keitaro.campaigns(offset=offset, limit=limit + 1)
    return [campaign_summary(keitaro, campaign) for campaign in campaigns[:limit]], len(campaigns) > limit


def open_campaign(db: Session, keitaro: KeitaroClient, campaign_id: int) -> EditorOut:
    """Читает кампанию и потоки из Keitaro, сверяет с ними черновики и отдаёт экран редактора."""
    try:
        campaign = keitaro.campaign(campaign_id)
        streams = keitaro.campaign_streams(campaign_id)
    except KeitaroError as error:
        if error.status_code == 404:
            raise ServiceError("Такой кампании нет в Keitaro.", status_code=404) from None
        raise

    streams.sort(key=lambda stream: (stream.get("position") or 0, stream["id"]))
    offer_stream_ids = [int(stream["id"]) for stream in streams if stream.get("schema") == OFFERS_SCHEMA]

    # Потоки, которых в кампании больше нет (или в них больше не офферы), забываем.
    db.execute(
        delete(StreamOffer).where(
            StreamOffer.campaign_id == campaign_id, StreamOffer.stream_id.not_in(offer_stream_ids)
        )
    )
    for stream in streams:
        if stream.get("schema") == OFFERS_SCHEMA:
            _sync_stream(db, campaign_id, stream)
    db.commit()

    names = keitaro.offer_names()
    return EditorOut(
        campaign=campaign_summary(keitaro, campaign),
        streams=[_stream_out(db, stream, names) for stream in streams],
    )


def _sync_stream(db: Session, campaign_id: int, stream: dict[str, Any]) -> None:
    """Переносит в базу то, что сейчас в потоке Keitaro. Неотправленный черновик не трогает."""
    stream_id = int(stream["id"])
    rows = {row.offer_id: row for row in _rows(db, stream_id)}
    had_unsent = any(row.unsent for row in rows.values())

    in_keitaro: dict[int, int] = {}
    for offer in stream.get("offers") or []:
        if offer.get("state", "active") == "active":
            in_keitaro[int(offer["offer_id"])] = int(offer.get("share") or 0)

    for offer_id, share in in_keitaro.items():
        row = rows.get(offer_id)
        is_new = row is None
        if row is None:
            row = StreamOffer(campaign_id=campaign_id, stream_id=stream_id, offer_id=offer_id)
            db.add(row)
        row.keitaro_share = share
        row.was_in_keitaro = True
        if is_new or not had_unsent:
            row.share = share
            row.removed = False

    for offer_id, row in rows.items():
        if offer_id in in_keitaro:
            continue
        # Оффер убрали прямо в Keitaro. Оставляем его у себя как убранный: его можно вернуть.
        row.keitaro_share = None
        if not had_unsent:
            row.removed = True
            row.share = 0
            row.pinned = False
    db.flush()


def _stream_out(db: Session, stream: dict[str, Any], names: dict[int, str]) -> EditorStream:
    schema = stream.get("schema")
    kind = "offers" if schema == OFFERS_SCHEMA else "redirect" if schema == REDIRECT_SCHEMA else "other"
    payload = stream.get("action_payload")
    return EditorStream(
        id=int(stream["id"]),
        name=str(stream.get("name") or f"Поток {stream['id']}"),
        position=int(stream.get("position") or 0),
        state=str(stream.get("state") or "active"),
        kind=kind,
        redirect_url=payload if kind == "redirect" and isinstance(payload, str) else None,
        filters=[
            StreamFilterOut(
                name=str(item.get("name", "")),
                mode=str(item.get("mode", "accept")),
                payload=[str(value) for value in item.get("payload") or []],
            )
            for item in stream.get("filters") or []
        ],
        offers=_offers_out(db, int(stream["id"]), names) if kind == "offers" else None,
    )


# Черновик потока -----------------------------------------------------------------


def _rows(db: Session, stream_id: int) -> list[StreamOffer]:
    return list(db.scalars(select(StreamOffer).where(StreamOffer.stream_id == stream_id).order_by(StreamOffer.id)))


def _row(db: Session, stream_id: int, offer_id: int) -> StreamOffer:
    row = db.scalar(
        select(StreamOffer).where(StreamOffer.stream_id == stream_id, StreamOffer.offer_id == offer_id)
    )
    if row is None:
        raise ServiceError("Такого оффера нет в этом потоке. Обновите страницу.", status_code=404)
    return row


def _rebalance(db: Session, stream_id: int) -> None:
    """Делит доли между офферами, которые остаются в потоке."""
    active = [row for row in _rows(db, stream_id) if not row.removed]
    shares = rebalance([row.share for row in active], [row.pinned for row in active])
    for row, share in zip(active, shares):
        row.share = share


def _status(row: StreamOffer) -> str:
    if row.removed:
        return "removing" if row.keitaro_share is not None else "removed"
    if row.keitaro_share is None:
        return "new"
    return "changed" if row.share != row.keitaro_share else "same"


def _offers_out(db: Session, stream_id: int, names: dict[int, str]) -> StreamOffersOut:
    rows = _rows(db, stream_id)
    # Сначала те, что в потоке, потом убранные. Внутри групп порядок не меняется, строки не прыгают.
    rows.sort(key=lambda row: row.removed)
    return StreamOffersOut(
        stream_id=stream_id,
        unsent=any(row.unsent for row in rows),
        total=sum(row.share for row in rows if not row.removed),
        items=[
            StreamOfferOut(
                offer_id=row.offer_id,
                name=names.get(row.offer_id) or f"Оффер {row.offer_id}",
                share=row.share,
                pinned=row.pinned,
                removed=row.removed,
                keitaro_share=row.keitaro_share,
                status=_status(row),
            )
            for row in rows
        ],
    )


def _finish(db: Session, keitaro: KeitaroClient, stream_id: int) -> StreamOffersOut:
    db.commit()
    return _offers_out(db, stream_id, keitaro.offer_names())


def add_offer(db: Session, keitaro: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int) -> StreamOffersOut:
    if keitaro.find_offer(offer_id) is None:
        raise ServiceError("Такого оффера нет в Keitaro. Выберите оффер из списка.", field="offer_id")

    row = db.scalar(select(StreamOffer).where(StreamOffer.stream_id == stream_id, StreamOffer.offer_id == offer_id))
    if row is not None and not row.removed:
        raise ServiceError("Этот оффер уже есть в потоке.", field="offer_id")
    if row is None:
        row = StreamOffer(campaign_id=campaign_id, stream_id=stream_id, offer_id=offer_id, share=0)
        db.add(row)
    row.removed = False
    row.pinned = False
    db.flush()
    _rebalance(db, stream_id)
    return _finish(db, keitaro, stream_id)


def remove_offer(db: Session, keitaro: KeitaroClient, stream_id: int, offer_id: int) -> StreamOffersOut:
    row = _row(db, stream_id, offer_id)
    if row.keitaro_share is None and not row.was_in_keitaro:
        # Добавили и передумали до отправки: в Keitaro его не было, помнить нечего.
        db.delete(row)
    else:
        row.removed = True
        row.share = 0
        row.pinned = False
    db.flush()
    _rebalance(db, stream_id)
    return _finish(db, keitaro, stream_id)


def restore_offer(db: Session, keitaro: KeitaroClient, stream_id: int, offer_id: int) -> StreamOffersOut:
    row = _row(db, stream_id, offer_id)
    row.removed = False
    db.flush()
    _rebalance(db, stream_id)
    return _finish(db, keitaro, stream_id)


def set_pinned(db: Session, keitaro: KeitaroClient, stream_id: int, offer_id: int, pinned: bool) -> StreamOffersOut:
    """Закреплённая доля не меняется при пересчёте. Само закрепление долей не двигает."""
    row = _row(db, stream_id, offer_id)
    if row.removed:
        raise ServiceError("Сначала верните оффер в поток.")
    row.pinned = pinned
    return _finish(db, keitaro, stream_id)


def cancel_changes(db: Session, keitaro: KeitaroClient, stream_id: int) -> StreamOffersOut:
    """Возвращает черновик к тому, что было в Keitaro при последней сверке."""
    for row in _rows(db, stream_id):
        if row.keitaro_share is not None:
            row.removed = False
            row.share = row.keitaro_share
        elif row.was_in_keitaro:
            row.removed = True
            row.share = 0
            row.pinned = False
        else:
            db.delete(row)
    return _finish(db, keitaro, stream_id)


def push_changes(db: Session, keitaro: KeitaroClient, stream_id: int) -> StreamOffersOut:
    """Отправляет черновик в Keitaro: состав офферов потока заменяется целиком."""
    rows = _rows(db, stream_id)
    active = [row for row in rows if not row.removed]
    if not active:
        raise ServiceError("В потоке должен остаться хотя бы один оффер. Добавьте оффер или отмените изменения.")

    # Убранные офферы в запрос не попадают совсем: из Keitaro они исчезают, а не остаются с нулевой долей.
    payload = [{"offer_id": row.offer_id, "share": row.share, "state": "active"} for row in active]
    keitaro.set_stream_offers(stream_id, payload)

    for row in rows:
        if row.removed:
            row.keitaro_share = None
        else:
            row.keitaro_share = row.share
            row.was_in_keitaro = True
    return _finish(db, keitaro, stream_id)
