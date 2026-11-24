"""Справочники, поиск офферов, настройки по умолчанию и разбор ошибок Keitaro."""

import pytest
from fastapi.testclient import TestClient

from app.keitaro import KeitaroClient, KeitaroError, normalize_base_url
from tests.conftest import KEITARO_URL


def test_bootstrap_before_setup(client):
    body = client.get("/api/bootstrap").json()

    assert body["keitaro_configured"] is True
    assert body["defaults"] is None
    assert body["redirect_url"] == "https://google.com"
    assert {"MX", "AU", "RO", "XK"} <= set(body["countries"])
    assert len(body["countries"]) == len(set(body["countries"])) == 250


def test_reference_lists(client):
    body = client.get("/api/reference").json()

    assert body["domains"] == [{"id": 1813, "name": "kt-emulator.test", "url": "https://kt-emulator.test"}]
    assert body["groups"] == [{"id": 10332, "name": "FORTESTS"}]
    assert body["traffic_sources"] == [{"id": 836, "name": "FORTESTS"}]


def test_defaults_are_saved_and_can_be_changed(client):
    payload = {"domain_id": 1813, "group_id": 10332, "traffic_source_id": 836}

    saved = client.put("/api/defaults", json=payload).json()
    again = client.put("/api/defaults", json=payload)

    assert saved["domain"]["url"] == "https://kt-emulator.test"
    assert again.status_code == 200
    assert client.get("/api/bootstrap").json()["defaults"] == saved


def test_defaults_reject_unknown_domain(client):
    response = client.put("/api/defaults", json={"domain_id": 1, "group_id": 10332, "traffic_source_id": 836})

    assert response.status_code == 422
    assert "domain_id" in response.json()["fields"]


def test_offer_search_by_words(client):
    body = client.get("/api/offers", params={"q": "detoxin prostate"}).json()

    assert [offer["id"] for offer in body["items"]] == [18008]
    assert body["items"][0]["countries"] == ["IN"]


def test_offer_search_by_number_puts_exact_match_first(client):
    body = client.get("/api/offers", params={"q": "18002"}).json()

    assert body["items"][0]["id"] == 18002


def test_offer_search_hides_deleted_and_respects_limit(client):
    everything = client.get("/api/offers").json()
    limited = client.get("/api/offers", params={"limit": 1}).json()

    assert 18099 not in [offer["id"] for offer in everything["items"]]
    assert everything["total"] == 6
    assert len(limited["items"]) == 1 and limited["total"] == 6


def test_wrong_api_key_is_explained(fake):
    keitaro = KeitaroClient(KEITARO_URL, "wrong", http=TestClient(fake, base_url=KEITARO_URL))

    with pytest.raises(KeitaroError) as error:
        keitaro.domains()

    assert "KEITARO_API_KEY" in error.value.message


def test_missing_settings_are_explained():
    with pytest.raises(KeitaroError) as error:
        KeitaroClient("", "").offers()

    assert ".env" in error.value.message


@pytest.mark.parametrize(
    "raw",
    [
        "https://tracker.test",
        "https://tracker.test/",
        "https://tracker.test/admin_api/v1",
        " https://tracker.test/admin_api/v1/ ",
    ],
)
def test_tracker_address_is_cleaned(raw):
    assert normalize_base_url(raw) == "https://tracker.test"


def test_page_files_are_always_revalidated(client):
    """После обновления приложения браузер не должен брать старые скрипты из своего кэша."""
    for path in ("/static/js/app.js", "/static/app.css", "/"):
        response = client.get(path)

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
