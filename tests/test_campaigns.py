"""Создание кампании: что уходит в Keitaro и что происходит при сбоях."""

GOOD = {"name": "MX nutra", "countries": ["mx", "AU"], "offer_id": 18001}


def test_creates_campaign_with_two_streams(client, fake, with_defaults):
    response = client.post("/api/campaigns", json=GOOD)

    assert response.status_code == 201
    state = fake.state.fake

    # Кампания: домен, группа и источник из настроек, ротация по позиции.
    (campaign_id, campaign), = state.campaigns.items()
    assert campaign["name"] == "MX nutra"
    assert campaign["domain_id"] == 1813
    assert campaign["group_id"] == 10332
    assert campaign["traffic_source_id"] == 836
    assert campaign["type"] == "position"
    assert len(campaign["alias"]) == 8

    geo, offer = state.streams

    # Поток 1: только выбранные страны, уходят на Google.
    assert geo["campaign_id"] == campaign_id
    assert geo["position"] == 1
    assert geo["schema"] == "redirect"
    assert geo["action_type"] == "http"
    assert geo["action_payload"] == "https://google.com"
    assert geo["filters"] == [{"name": "country", "mode": "accept", "payload": ["MX", "AU"]}]

    # Поток 2: все остальные, на выбранный оффер целиком.
    assert offer["campaign_id"] == campaign_id
    assert offer["position"] == 2
    assert offer["schema"] == "landings"
    assert offer["offers"] == [{"offer_id": 18001, "share": 100, "state": "active"}]
    assert "filters" not in offer

    body = response.json()
    assert body["url"] == f"https://kt-emulator.test/{campaign['alias']}"
    assert body["admin_url"] == f"https://tracker.test/admin/#!/campaign.editor/{campaign_id}"
    assert body["countries"] == ["MX", "AU"]


def test_created_campaign_appears_in_history(client, with_defaults):
    client.post("/api/campaigns", json=GOOD)
    client.post("/api/campaigns", json={**GOOD, "name": "Вторая"})

    history = client.get("/api/campaigns").json()

    assert [item["name"] for item in history] == ["Вторая", "MX nutra"]
    assert history[0]["offer_name"].startswith("18001 Detoxin")
    assert history[0]["domain_name"] == "kt-emulator.test"


def test_failed_stream_removes_half_made_campaign(client, fake, with_defaults):
    state = fake.state.fake
    state.fail_stream_number = 2  # поток с оффером Keitaro отклонит

    response = client.post("/api/campaigns", json=GOOD)

    assert response.status_code == 502
    assert "заготовку мы убрали" in response.json()["detail"]
    assert state.campaigns == {}  # в Keitaro не осталось кампании с одним потоком
    assert len(state.deleted) == 1
    assert client.get("/api/campaigns").json() == []  # и в нашей истории её нет


def test_needs_defaults_first(client, fake):
    response = client.post("/api/campaigns", json=GOOD)

    assert response.status_code == 409
    assert "defaults" in response.json()["fields"]
    assert fake.state.fake.campaigns == {}


def test_rejects_bad_form(client, fake, with_defaults):
    response = client.post("/api/campaigns", json={"name": "   ", "countries": ["zz", "au"], "offer_id": 0})

    assert response.status_code == 422
    fields = response.json()["fields"]
    assert fields["name"] == "Введите название кампании."
    assert "ZZ" in fields["countries"]
    assert fields["offer_id"] == "Выберите оффер."
    assert fake.state.fake.campaigns == {}


def test_rejects_unknown_offer(client, fake, with_defaults):
    response = client.post("/api/campaigns", json={**GOOD, "offer_id": 99999})

    assert response.status_code == 422
    assert "offer_id" in response.json()["fields"]
    assert fake.state.fake.campaigns == {}


def test_rejects_deleted_offer(client, with_defaults):
    response = client.post("/api/campaigns", json={**GOOD, "offer_id": 18099})

    assert response.status_code == 422


def test_duplicate_name_is_shown_under_name_field(client, with_defaults):
    client.post("/api/campaigns", json=GOOD)

    response = client.post("/api/campaigns", json=GOOD)

    assert response.status_code == 422
    assert "already exists" in response.json()["fields"]["name"]


def test_many_countries_keep_stream_name_short(client, fake, with_defaults):
    countries = ["MX", "AU", "RO", "DE", "FR", "IT", "ES", "PL"]

    client.post("/api/campaigns", json={**GOOD, "countries": countries})

    geo = fake.state.fake.streams[0]
    assert geo["name"] == "Гео MX, AU, RO, DE, FR, IT и ещё 2"
    assert geo["filters"][0]["payload"] == countries
