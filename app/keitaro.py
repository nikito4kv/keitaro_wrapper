"""Клиент Admin API трекера Keitaro.

Документация: https://admin-api.docs.keitaro.io/
Все запросы идут на <адрес трекера>/admin_api/v1 с ключом в заголовке Api-Key.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings

API_PREFIX = "/admin_api/v1"


class KeitaroError(Exception):
    """Keitaro недоступен или отказался выполнять запрос. Текст готов для показа человеку."""

    def __init__(self, message: str, *, status_code: int | None = None, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        # Замечания Keitaro к отдельным полям запроса, например {"name": "уже занято"}.
        self.fields = fields or {}


def normalize_base_url(url: str) -> str:
    """Приводит адрес трекера к виду https://tracker.example.com без хвостов."""
    url = url.strip().rstrip("/")
    if url.endswith(API_PREFIX):
        url = url[: -len(API_PREFIX)]
    return url.rstrip("/")


class KeitaroClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 15.0,
        http: httpx.Client | None = None,
        cache_ttl: float = 60.0,
    ):
        self.base_url = normalize_base_url(base_url)
        self._api_key = api_key.strip()
        self._http = http or httpx.Client(base_url=self.base_url or "http://keitaro.invalid", timeout=timeout)
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self._api_key)

    # Справочники ---------------------------------------------------------

    def offers(self) -> list[dict[str, Any]]:
        """Офферы, которые можно выбирать: без удалённых и архивных."""
        return [offer for offer in self._catalog() if offer["active"]]

    def find_offer(self, offer_id: int) -> dict[str, Any] | None:
        for attempt in range(2):
            for offer in self.offers():
                if offer["id"] == offer_id:
                    return offer
            if attempt == 0:
                # Оффер могли завести только что, а список у нас из кэша.
                self.forget("offers")
        return None

    def offer_names(self) -> dict[int, str]:
        """Названия всех офферов, включая удалённые: они могут до сих пор стоять в потоках."""
        return {offer["id"]: offer["name"] for offer in self._catalog()}

    def _catalog(self) -> list[dict[str, Any]]:
        return self._cached("offers", self._load_offers)

    def domains(self) -> list[dict[str, Any]]:
        return self._cached("domains", self._load_domains)

    def campaign_groups(self) -> list[dict[str, Any]]:
        return self._cached("groups", self._load_groups)

    def traffic_sources(self) -> list[dict[str, Any]]:
        return self._cached("traffic_sources", self._load_traffic_sources)

    def forget(self, key: str | None = None) -> None:
        """Сбрасывает кэш справочников: один список или все сразу."""
        with self._lock:
            if key is None:
                self._cache.clear()
            else:
                self._cache.pop(key, None)

    # Создание ------------------------------------------------------------

    def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/campaigns", json=payload)

    def create_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/streams", json=payload)

    def delete_campaign(self, campaign_id: int) -> None:
        """В настоящем Keitaro это перенос в архив, откуда кампанию можно вернуть."""
        self._request("DELETE", f"/campaigns/{campaign_id}")

    def campaign_admin_url(self, campaign_id: int) -> str:
        return f"{self.base_url}/admin/#!/campaign.editor/{campaign_id}"

    # Существующие кампании и их потоки -------------------------------------

    def campaigns(self, *, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return self._list("/campaigns", params={"offset": offset, "limit": limit})

    def campaign(self, campaign_id: int) -> dict[str, Any]:
        return self._request("GET", f"/campaigns/{campaign_id}")

    def campaign_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        return self._list(f"/campaigns/{campaign_id}/streams")

    def set_stream_offers(self, stream_id: int, offers: list[dict[str, Any]]) -> dict[str, Any]:
        """Заменяет состав офферов потока целиком: чего нет в списке, того не будет в потоке."""
        return self._request("PUT", f"/streams/{stream_id}", json={"offers": offers})

    # Внутреннее ----------------------------------------------------------

    def _load_offers(self) -> list[dict[str, Any]]:
        offers = []
        for item in self._list("/offers"):
            country = item.get("country") or []
            if isinstance(country, str):
                country = [country]
            offers.append(
                {
                    "id": int(item["id"]),
                    "name": str(item.get("name", "")),
                    "countries": list(country),
                    "active": item.get("state", "active") == "active" and not item.get("archive"),
                }
            )
        return offers

    def _load_domains(self) -> list[dict[str, Any]]:
        domains = []
        for item in self._list("/domains"):
            if item.get("state", "active") != "active":
                continue
            name = str(item.get("name", "")).strip().rstrip("/")
            if name.startswith(("http://", "https://")):
                url = name
                name = name.split("://", 1)[1]
            else:
                scheme = "https" if item.get("is_ssl", True) else "http"
                url = f"{scheme}://{name}"
            domains.append({"id": int(item["id"]), "name": name, "url": url})
        return domains

    def _load_groups(self) -> list[dict[str, Any]]:
        items = self._list("/groups", params={"type": "campaigns"})
        return [{"id": int(item["id"]), "name": str(item.get("name", ""))} for item in items]

    def _load_traffic_sources(self) -> list[dict[str, Any]]:
        return [
            {"id": int(item["id"]), "name": str(item.get("name", ""))}
            for item in self._list("/traffic_sources")
            if item.get("state", "active") == "active"
        ]

    def _cached(self, key: str, loader: Callable[[], Any]) -> Any:
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < self._cache_ttl:
                return hit[1]
        value = loader()
        with self._lock:
            self._cache[key] = (time.monotonic(), value)
        return value

    def _list(self, path: str, **kwargs: Any) -> list[dict[str, Any]]:
        data = self._request("GET", path, **kwargs)
        if not isinstance(data, list):
            raise KeitaroError("Keitaro ответил не списком. Проверьте адрес трекера в KEITARO_URL.")
        return data

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.configured:
            raise KeitaroError(
                "Не указан адрес или ключ Keitaro. Заполните KEITARO_URL и KEITARO_API_KEY "
                "в файле .env и перезапустите приложение."
            )
        headers = {"Api-Key": self._api_key, "Accept": "application/json"}
        try:
            response = self._http.request(method, API_PREFIX + path, headers=headers, **kwargs)
        except httpx.TimeoutException:
            raise KeitaroError(f"Keitaro не ответил вовремя ({self.base_url}). Попробуйте ещё раз.") from None
        except httpx.HTTPError:
            raise KeitaroError(
                f"Не удалось связаться с Keitaro по адресу {self.base_url}. "
                "Проверьте KEITARO_URL и доступ к трекеру."
            ) from None

        if response.status_code >= 400:
            raise self._error_from(response)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise KeitaroError(
                "Keitaro ответил не в формате JSON. Проверьте адрес трекера в KEITARO_URL."
            ) from None

    @staticmethod
    def _error_from(response: httpx.Response) -> KeitaroError:
        code = response.status_code
        if code == 401:
            return KeitaroError("Keitaro не принял ключ API. Проверьте KEITARO_API_KEY.", status_code=code)
        if code == 402:
            return KeitaroError("В этой редакции Keitaro нет Admin API.", status_code=code)

        try:
            body = response.json()
        except ValueError:
            body = None

        if isinstance(body, dict):
            # Обычная ошибка: {"error": "..."}
            error = body.get("error") or body.get("detail")
            if isinstance(error, str) and error:
                return KeitaroError(f"Keitaro отклонил запрос: {error}", status_code=code)
            # Ошибка проверки полей (406): {"name": ["..."]}
            fields = {
                str(field): "; ".join(map(str, notes)) if isinstance(notes, list) else str(notes)
                for field, notes in body.items()
            }
            if fields:
                summary = "; ".join(f"{field}: {note}" for field, note in fields.items())
                return KeitaroError(f"Keitaro отклонил запрос. {summary}", status_code=code, fields=fields)

        return KeitaroError(f"Keitaro вернул ошибку {code}.", status_code=code)


@lru_cache
def get_keitaro() -> KeitaroClient:
    settings = get_settings()
    return KeitaroClient(settings.keitaro_url, settings.keitaro_api_key, timeout=settings.keitaro_timeout)
