"""Адреса нашего API. Всё лежит под /api."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import editor, services
from app.config import Settings, get_settings
from app.countries import COUNTRY_CODES
from app.db import get_db
from app.keitaro import KeitaroClient, get_keitaro
from app.models import CampaignDefaults, CreatedCampaign
from app.schemas import (
    Bootstrap,
    CampaignIn,
    CampaignOut,
    DefaultsIn,
    DefaultsOut,
    EditorOut,
    OfferRef,
    OfferSearchResult,
    PinIn,
    Reference,
    StreamOffersOut,
    TrackerCampaignList,
)

router = APIRouter(prefix="/api")

Db = Annotated[Session, Depends(get_db)]
Keitaro = Annotated[KeitaroClient, Depends(get_keitaro)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _defaults_out(defaults: CampaignDefaults | None) -> DefaultsOut | None:
    if defaults is None:
        return None
    return DefaultsOut(
        domain={"id": defaults.domain_id, "name": defaults.domain_name, "url": defaults.domain_url},
        group={"id": defaults.group_id, "name": defaults.group_name},
        traffic_source={"id": defaults.traffic_source_id, "name": defaults.traffic_source_name},
    )


def _campaign_out(record: CreatedCampaign, keitaro: KeitaroClient) -> CampaignOut:
    out = CampaignOut.model_validate(record)
    out.admin_url = keitaro.campaign_admin_url(record.keitaro_campaign_id)
    return out


@router.get("/bootstrap", response_model=Bootstrap)
def bootstrap(db: Db, keitaro: Keitaro, settings: AppSettings):
    return Bootstrap(
        keitaro_url=keitaro.base_url,
        keitaro_configured=keitaro.configured,
        redirect_url=settings.geo_redirect_url,
        countries=list(COUNTRY_CODES),
        defaults=_defaults_out(services.get_defaults(db)),
    )


@router.get("/reference", response_model=Reference)
def reference(keitaro: Keitaro, refresh: bool = False):
    if refresh:
        keitaro.forget()
    return Reference(
        domains=keitaro.domains(),
        groups=keitaro.campaign_groups(),
        traffic_sources=keitaro.traffic_sources(),
    )


@router.get("/offers", response_model=OfferSearchResult)
def offers(keitaro: Keitaro, q: str = "", limit: Annotated[int, Query(ge=1, le=50)] = 20):
    items, total = services.search_offers(keitaro, q, limit)
    return OfferSearchResult(items=items, total=total)


@router.put("/defaults", response_model=DefaultsOut)
def save_defaults(data: DefaultsIn, db: Db, keitaro: Keitaro):
    return _defaults_out(services.save_defaults(db, keitaro, data))


@router.get("/campaigns", response_model=list[CampaignOut])
def campaigns(db: Db, keitaro: Keitaro, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return [_campaign_out(record, keitaro) for record in services.list_created(db, limit)]


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(data: CampaignIn, db: Db, keitaro: Keitaro, settings: AppSettings):
    record = services.create_campaign(db, keitaro, data, settings.geo_redirect_url)
    return _campaign_out(record, keitaro)


# Редактор офферов существующей кампании ------------------------------------


@router.get("/editor/campaigns", response_model=TrackerCampaignList)
def editor_campaigns(
    keitaro: Keitaro,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    items, has_more = editor.list_campaigns(keitaro, offset, limit)
    return TrackerCampaignList(items=items, has_more=has_more)


@router.get("/editor/campaigns/{campaign_id}", response_model=EditorOut)
def editor_campaign(campaign_id: int, db: Db, keitaro: Keitaro):
    """Сверяет потоки кампании с Keitaro и отдаёт экран редактора."""
    return editor.open_campaign(db, keitaro, campaign_id)


@router.post("/editor/campaigns/{campaign_id}/streams/{stream_id}/offers", response_model=StreamOffersOut)
def editor_add_offer(campaign_id: int, stream_id: int, data: OfferRef, db: Db, keitaro: Keitaro):
    return editor.add_offer(db, keitaro, campaign_id, stream_id, data.offer_id)


@router.delete("/editor/streams/{stream_id}/offers/{offer_id}", response_model=StreamOffersOut)
def editor_remove_offer(stream_id: int, offer_id: int, db: Db, keitaro: Keitaro):
    return editor.remove_offer(db, keitaro, stream_id, offer_id)


@router.post("/editor/streams/{stream_id}/offers/{offer_id}/restore", response_model=StreamOffersOut)
def editor_restore_offer(stream_id: int, offer_id: int, db: Db, keitaro: Keitaro):
    return editor.restore_offer(db, keitaro, stream_id, offer_id)


@router.put("/editor/streams/{stream_id}/offers/{offer_id}/pin", response_model=StreamOffersOut)
def editor_pin_offer(stream_id: int, offer_id: int, data: PinIn, db: Db, keitaro: Keitaro):
    return editor.set_pinned(db, keitaro, stream_id, offer_id, data.pinned)


@router.post("/editor/streams/{stream_id}/cancel", response_model=StreamOffersOut)
def editor_cancel(stream_id: int, db: Db, keitaro: Keitaro):
    return editor.cancel_changes(db, keitaro, stream_id)


@router.post("/editor/streams/{stream_id}/push", response_model=StreamOffersOut)
def editor_push(stream_id: int, db: Db, keitaro: Keitaro):
    return editor.push_changes(db, keitaro, stream_id)
