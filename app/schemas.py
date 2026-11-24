"""Форматы запросов и ответов нашего API."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from app.countries import COUNTRY_CODE_SET


class NamedItem(BaseModel):
    id: int
    name: str


class DomainItem(NamedItem):
    url: str


class OfferItem(NamedItem):
    countries: list[str]


class OfferSearchResult(BaseModel):
    items: list[OfferItem]
    total: int


class Reference(BaseModel):
    """Справочники Keitaro, из которых выбираются домен, группа и источник."""

    domains: list[DomainItem]
    groups: list[NamedItem]
    traffic_sources: list[NamedItem]


class DefaultsIn(BaseModel):
    domain_id: int
    group_id: int
    traffic_source_id: int


class DefaultsOut(BaseModel):
    domain: DomainItem
    group: NamedItem
    traffic_source: NamedItem


class Bootstrap(BaseModel):
    """Всё, что странице нужно при открытии и что не требует похода в Keitaro."""

    keitaro_url: str
    keitaro_configured: bool
    redirect_url: str
    countries: list[str]
    defaults: DefaultsOut | None


class CampaignIn(BaseModel):
    name: str
    countries: list[str]
    offer_id: int

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Введите название кампании.")
        if len(value) > 255:
            raise ValueError("Название длиннее 255 символов.")
        return value

    @field_validator("countries")
    @classmethod
    def clean_countries(cls, value: list[str]) -> list[str]:
        codes: list[str] = []
        for raw in value:
            code = raw.strip().upper()
            if code and code not in codes:
                codes.append(code)
        if not codes:
            raise ValueError("Выберите хотя бы одну страну.")
        unknown = [code for code in codes if code not in COUNTRY_CODE_SET]
        if unknown:
            raise ValueError(f"Нет стран с кодами: {', '.join(unknown)}.")
        return codes

    @field_validator("offer_id")
    @classmethod
    def check_offer_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Выберите оффер.")
        return value


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keitaro_campaign_id: int
    name: str
    url: str
    admin_url: str = ""
    countries: list[str]
    redirect_url: str
    offer_id: int
    offer_name: str
    domain_name: str
    group_name: str
    traffic_source_name: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        # SQLite возвращает время без часового пояса. Мы всегда пишем UTC.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


# Редактор офферов существующей кампании -----------------------------------


class TrackerCampaign(BaseModel):
    """Кампания из Keitaro в списке «Кампании»."""

    id: int
    name: str
    state: str
    created_at: str | None
    url: str | None
    admin_url: str


class TrackerCampaignList(BaseModel):
    items: list[TrackerCampaign]
    has_more: bool


class StreamOfferOut(BaseModel):
    offer_id: int
    name: str
    share: int
    pinned: bool
    removed: bool
    # Доля в Keitaro при последней сверке. None: в потоке трекера этого оффера нет.
    keitaro_share: int | None
    # same: как в Keitaro; new: добавлен; changed: доля изменилась;
    # removing: будет убран при отправке; removed: убран, можно вернуть.
    status: str


class StreamOffersOut(BaseModel):
    stream_id: int
    unsent: bool
    total: int
    items: list[StreamOfferOut]


class StreamFilterOut(BaseModel):
    name: str
    mode: str
    payload: list[str]


class EditorStream(BaseModel):
    id: int
    name: str
    position: int
    state: str
    # offers: поток с офферами, его можно править; redirect: отправляет по ссылке; other: всё остальное.
    kind: str
    redirect_url: str | None
    filters: list[StreamFilterOut]
    offers: StreamOffersOut | None


class EditorOut(BaseModel):
    campaign: TrackerCampaign
    streams: list[EditorStream]


class OfferRef(BaseModel):
    offer_id: int


class PinIn(BaseModel):
    pinned: bool
