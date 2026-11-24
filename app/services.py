"""Что приложение умеет делать: хранить настройки по умолчанию и создавать кампании в Keitaro."""

from __future__ import annotations

import logging
import secrets
import string
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.keitaro import KeitaroClient, KeitaroError
from app.models import CampaignDefaults, CreatedCampaign
from app.schemas import CampaignIn, DefaultsIn

log = logging.getLogger(__name__)

ALIAS_ALPHABET = string.ascii_letters + string.digits

# Как поля Keitaro называются в нашей форме. Нужно, чтобы замечание Keitaro
# («такое название уже есть») показать под нужным полем.
KEITARO_FIELD_TO_FORM = {"name": "name"}


class ServiceError(Exception):
    """Запрос нельзя выполнить по понятной человеку причине."""

    def __init__(self, message: str, *, field: str | None = None, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.field = field
        self.status_code = status_code


# Домен, группа и источник по умолчанию ------------------------------------


def get_defaults(db: Session) -> CampaignDefaults | None:
    return db.get(CampaignDefaults, CampaignDefaults.SINGLETON_ID)


def save_defaults(db: Session, keitaro: KeitaroClient, data: DefaultsIn) -> CampaignDefaults:
    domain = _pick(keitaro.domains(), data.domain_id, "Такого домена нет в Keitaro.", "domain_id")
    group = _pick(keitaro.campaign_groups(), data.group_id, "Такой группы нет в Keitaro.", "group_id")
    source = _pick(
        keitaro.traffic_sources(), data.traffic_source_id, "Такого источника нет в Keitaro.", "traffic_source_id"
    )

    defaults = get_defaults(db)
    if defaults is None:
        defaults = CampaignDefaults(id=CampaignDefaults.SINGLETON_ID)
        db.add(defaults)

    defaults.domain_id = domain["id"]
    defaults.domain_name = domain["name"]
    defaults.domain_url = domain["url"]
    defaults.group_id = group["id"]
    defaults.group_name = group["name"]
    defaults.traffic_source_id = source["id"]
    defaults.traffic_source_name = source["name"]
    db.commit()
    return defaults


def _pick(items: list[dict[str, Any]], item_id: int, message: str, field: str) -> dict[str, Any]:
    for item in items:
        if item["id"] == item_id:
            return item
    raise ServiceError(message, field=field)


# Поиск офферов --------------------------------------------------------------


def search_offers(keitaro: KeitaroClient, query: str, limit: int) -> tuple[list[dict[str, Any]], int]:
    """Ищет по номеру и названию. Все слова запроса должны встретиться в оффере."""
    words = query.lower().split()
    offers = keitaro.offers()
    if words:
        offers = [
            offer
            for offer in offers
            if all(word in f"{offer['id']} {offer['name']}".lower() for word in words)
        ]
        first = words[0]
        # Точное совпадение номера выше совпадения по началу номера, остальное по порядку Keitaro.
        offers.sort(key=lambda offer: (str(offer["id"]) != first, not str(offer["id"]).startswith(first)))
    return offers[:limit], len(offers)


# Создание кампании ----------------------------------------------------------


def generate_alias(length: int = 8) -> str:
    """Короткий идентификатор кампании: хвост её ссылки, как wVqN1R в Keitaro."""
    return "".join(secrets.choice(ALIAS_ALPHABET) for _ in range(length))


def build_campaign_payload(data: CampaignIn, defaults: CampaignDefaults, alias: str) -> dict[str, Any]:
    return {
        "name": data.name,
        "alias": alias,
        "type": "position",
        "state": "active",
        "cost_type": "CPC",
        "cost_auto": True,
        "domain_id": defaults.domain_id,
        "group_id": defaults.group_id,
        "traffic_source_id": defaults.traffic_source_id,
    }


def build_geo_stream_payload(campaign_id: int, countries: list[str], redirect_url: str) -> dict[str, Any]:
    """Первый поток: посетители из выбранных стран уходят по ссылке."""
    return {
        "campaign_id": campaign_id,
        "name": f"Гео {_short_list(countries)}",
        "type": "regular",
        "position": 1,
        "state": "active",
        "schema": "redirect",
        "action_type": "http",
        "action_payload": redirect_url,
        "collect_clicks": True,
        "filter_or": False,
        "filters": [{"name": "country", "mode": "accept", "payload": countries}],
    }


def build_offer_stream_payload(campaign_id: int, offer_id: int) -> dict[str, Any]:
    """Второй поток: все остальные посетители попадают на оффер."""
    return {
        "campaign_id": campaign_id,
        # Название без номера оффера: состав потока потом меняют в редакторе.
        "name": "Офферы",
        "type": "default",
        "position": 2,
        "state": "active",
        "schema": "landings",
        "action_type": "http",
        "collect_clicks": True,
        "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
    }


def _short_list(codes: list[str], shown: int = 6) -> str:
    if len(codes) <= shown:
        return ", ".join(codes)
    return f"{', '.join(codes[:shown])} и ещё {len(codes) - shown}"


def create_campaign(db: Session, keitaro: KeitaroClient, data: CampaignIn, redirect_url: str) -> CreatedCampaign:
    defaults = get_defaults(db)
    if defaults is None:
        raise ServiceError("Сначала выберите домен, группу и источник.", field="defaults", status_code=409)

    offer = keitaro.find_offer(data.offer_id)
    if offer is None:
        raise ServiceError("Такого оффера нет в Keitaro. Выберите оффер из списка.", field="offer_id")

    alias = generate_alias()
    try:
        campaign = keitaro.create_campaign(build_campaign_payload(data, defaults, alias))
    except KeitaroError as error:
        for keitaro_field, form_field in KEITARO_FIELD_TO_FORM.items():
            if keitaro_field in error.fields:
                raise ServiceError(
                    f"Keitaro не принял это значение: {error.fields[keitaro_field]}", field=form_field
                ) from None
        raise

    campaign_id = int(campaign["id"])
    alias = campaign.get("alias") or alias

    try:
        keitaro.create_stream(build_geo_stream_payload(campaign_id, data.countries, redirect_url))
        keitaro.create_stream(build_offer_stream_payload(campaign_id, data.offer_id))
    except KeitaroError as error:
        # Кампания без потоков никому не нужна и только запутает. Убираем за собой.
        raise KeitaroError(f"{error.message} {_roll_back(keitaro, campaign_id, data.name)}") from None

    record = CreatedCampaign(
        keitaro_campaign_id=campaign_id,
        name=campaign.get("name") or data.name,
        alias=alias,
        url=f"{defaults.domain_url}/{alias}",
        countries=data.countries,
        redirect_url=redirect_url,
        offer_id=offer["id"],
        offer_name=offer["name"],
        domain_name=defaults.domain_name,
        group_name=defaults.group_name,
        traffic_source_name=defaults.traffic_source_name,
    )
    db.add(record)
    db.commit()
    return record


def _roll_back(keitaro: KeitaroClient, campaign_id: int, name: str) -> str:
    """Убирает недоделанную кампанию и возвращает фразу о том, чем это кончилось."""
    try:
        keitaro.delete_campaign(campaign_id)
    except KeitaroError:
        log.exception("Не удалось убрать недоделанную кампанию %s", campaign_id)
        return (
            f"Кампания «{name}» (номер {campaign_id}) осталась в Keitaro без потоков. "
            "Удалите её вручную."
        )
    return "Кампания не создана, недоделанную заготовку мы убрали."


def list_created(db: Session, limit: int) -> list[CreatedCampaign]:
    query = select(CreatedCampaign).order_by(CreatedCampaign.created_at.desc(), CreatedCampaign.id.desc())
    return list(db.scalars(query.limit(limit)))
