"""Редактор офферов существующей кампании.

Главный тест повторяет по шагам видео с работающим редактором и сверяет цифры с ним.
Номера офферов свои (18001…18005), роли те же, что у офферов в видео.
"""

import pytest

A, B, C, D, E = 18001, 18002, 18003, 18004, 18005


@pytest.fixture
def campaign(client, fake, with_defaults):
    """Кампания с тремя офферами в потоке, как в начале видео: 33 / 33 / 34."""
    created = client.post("/api/campaigns", json={"name": "campaign 2", "countries": ["AU"], "offer_id": A}).json()
    state = fake.state.fake
    stream_id = next(key for key, stream in state.stored_streams.items() if stream["schema"] == "landings")
    state.set_offers(
        stream_id,
        [{"offer_id": A, "share": 33}, {"offer_id": B, "share": 33}, {"offer_id": C, "share": 34}],
    )
    return {"id": created["keitaro_campaign_id"], "stream": stream_id}


def shares(offers: dict) -> dict[int, int]:
    """Доли офферов, которые остаются в потоке."""
    return {item["offer_id"]: item["share"] for item in offers["items"] if not item["removed"]}


def removed(offers: dict) -> list[int]:
    return [item["offer_id"] for item in offers["items"] if item["removed"]]


def open_editor(client, campaign) -> dict:
    """Открывает кампанию и возвращает её поток с офферами."""
    response = client.get(f"/api/editor/campaigns/{campaign['id']}")
    assert response.status_code == 200
    return next(stream for stream in response.json()["streams"] if stream["id"] == campaign["stream"])["offers"]


def add(client, campaign, offer_id) -> dict:
    url = f"/api/editor/campaigns/{campaign['id']}/streams/{campaign['stream']}/offers"
    response = client.post(url, json={"offer_id": offer_id})
    assert response.status_code == 200, response.json()
    return response.json()


def act(client, campaign, method, tail, **kwargs) -> dict:
    response = client.request(method, f"/api/editor/streams/{campaign['stream']}{tail}", **kwargs)
    assert response.status_code == 200, response.json()
    return response.json()


def in_keitaro(fake, campaign) -> dict[int, int]:
    rows = fake.state.fake.stored_streams[campaign["stream"]]["offers"]
    return {row["offer_id"]: row["share"] for row in rows}


def test_walkthrough_from_the_video(client, fake, campaign):
    state = fake.state.fake

    # Открыли кампанию: в редакторе то же, что в Keitaro.
    offers = open_editor(client, campaign)
    assert shares(offers) == {A: 33, B: 33, C: 34}
    assert offers["unsent"] is False

    # Добавили четвёртый оффер: всем по 25. В Keitaro пока ничего не ушло.
    offers = add(client, campaign, D)
    assert shares(offers) == {A: 25, B: 25, C: 25, D: 25}
    assert offers["unsent"] is True
    assert state.puts == []
    assert in_keitaro(fake, campaign) == {A: 33, B: 33, C: 34}

    # Отправили: в Keitaro те же четыре по 25.
    offers = act(client, campaign, "POST", "/push")
    assert offers["unsent"] is False
    assert in_keitaro(fake, campaign) == {A: 25, B: 25, C: 25, D: 25}

    # Добавили пятый (по 20) и передумали: «Отменить» возвращает четыре по 25.
    assert shares(add(client, campaign, E)) == {A: 20, B: 20, C: 20, D: 20, E: 20}
    offers = act(client, campaign, "POST", "/cancel")
    assert shares(offers) == {A: 25, B: 25, C: 25, D: 25}
    assert removed(offers) == []
    assert offers["unsent"] is False

    # Убрали второй оффер: оставшиеся делят 100 как 33 / 33 / 34, убранный остаётся с нулём.
    offers = act(client, campaign, "DELETE", f"/offers/{B}")
    assert shares(offers) == {A: 33, C: 33, D: 34}
    assert removed(offers) == [B]
    assert next(item for item in offers["items"] if item["offer_id"] == B)["share"] == 0

    # Отправили: из Keitaro оффер исчез совсем, а не остался с нулевой долей.
    act(client, campaign, "POST", "/push")
    assert state.puts[-1] == (
        campaign["stream"],
        {
            "offers": [
                {"offer_id": A, "share": 33, "state": "active"},
                {"offer_id": C, "share": 33, "state": "active"},
                {"offer_id": D, "share": 34, "state": "active"},
            ]
        },
    )
    assert in_keitaro(fake, campaign) == {A: 33, C: 33, D: 34}

    # Вернули убранный: снова четыре по 25. Отправили.
    offers = act(client, campaign, "POST", f"/offers/{B}/restore")
    assert shares(offers) == {A: 25, B: 25, C: 25, D: 25}
    act(client, campaign, "POST", "/push")
    assert in_keitaro(fake, campaign) == {A: 25, B: 25, C: 25, D: 25}

    # Два оффера убрали прямо в Keitaro. После сверки редактор показывает их убранными,
    # а доли оставшихся не трогает: 25 и 25, как в трекере.
    state.set_offers(campaign["stream"], [{"offer_id": D, "share": 25}, {"offer_id": B, "share": 25}])
    offers = open_editor(client, campaign)
    assert shares(offers) == {B: 25, D: 25}
    assert removed(offers) == [A, C]
    assert offers["unsent"] is False

    # Закрепили долю одного: само закрепление ничего не пересчитывает и отправлять нечего.
    offers = act(client, campaign, "PUT", f"/offers/{B}/pin", json={"pinned": True})
    assert shares(offers) == {B: 25, D: 25}
    assert offers["unsent"] is False

    # Вернули первый: закреплённые 25 на месте, двое свободных делят 75 как 38 и 37.
    offers = act(client, campaign, "POST", f"/offers/{A}/restore")
    assert shares(offers) == {A: 38, B: 25, D: 37}
    assert removed(offers) == [C]

    act(client, campaign, "POST", "/push")
    assert in_keitaro(fake, campaign) == {A: 38, B: 25, D: 37}


def test_statuses_show_what_will_change(client, campaign):
    open_editor(client, campaign)
    add(client, campaign, D)
    offers = act(client, campaign, "DELETE", f"/offers/{B}")

    by_offer = {item["offer_id"]: item for item in offers["items"]}
    assert by_offer[D]["status"] == "new" and by_offer[D]["keitaro_share"] is None
    assert by_offer[B]["status"] == "removing" and by_offer[B]["keitaro_share"] == 33
    assert by_offer[A]["status"] == "same"  # была 33 и осталась 33
    assert by_offer[C]["status"] == "changed" and by_offer[C]["keitaro_share"] == 34 and by_offer[C]["share"] == 33

    offers = act(client, campaign, "POST", "/push")
    by_offer = {item["offer_id"]: item for item in offers["items"]}
    assert by_offer[B]["status"] == "removed"
    assert {by_offer[key]["status"] for key in (A, C, D)} == {"same"}


def test_offer_added_by_mistake_leaves_no_trace(client, campaign):
    open_editor(client, campaign)
    add(client, campaign, D)

    offers = act(client, campaign, "DELETE", f"/offers/{D}")

    assert shares(offers) == {A: 33, B: 33, C: 34}
    assert removed(offers) == []
    assert offers["unsent"] is False


def test_cannot_add_same_offer_twice(client, campaign):
    open_editor(client, campaign)
    url = f"/api/editor/campaigns/{campaign['id']}/streams/{campaign['stream']}/offers"

    response = client.post(url, json={"offer_id": A})

    assert response.status_code == 422
    assert "уже есть" in response.json()["detail"]


def test_cannot_add_unknown_or_deleted_offer(client, campaign):
    open_editor(client, campaign)
    url = f"/api/editor/campaigns/{campaign['id']}/streams/{campaign['stream']}/offers"

    assert client.post(url, json={"offer_id": 99999}).status_code == 422
    assert client.post(url, json={"offer_id": 18099}).status_code == 422


def test_adding_removed_offer_brings_it_back(client, campaign):
    open_editor(client, campaign)
    act(client, campaign, "DELETE", f"/offers/{B}")
    act(client, campaign, "POST", "/push")

    offers = add(client, campaign, B)

    assert shares(offers) == {A: 33, B: 33, C: 34}
    assert removed(offers) == []


def test_stream_can_be_emptied_and_filled_again(client, fake, campaign):
    """Тупика нет: из потока можно убрать все офферы, отправить, а потом добавить оффер снова."""
    open_editor(client, campaign)
    for offer_id in (A, B, C):
        act(client, campaign, "DELETE", f"/offers/{offer_id}")

    offers = act(client, campaign, "POST", "/push")

    assert fake.state.fake.puts[-1] == (campaign["stream"], {"offers": []})
    assert in_keitaro(fake, campaign) == {}
    assert shares(offers) == {} and removed(offers) == [A, B, C]

    # Открыли кампанию заново: поток на месте, просто пустой. Добавляем новый оффер.
    assert shares(open_editor(client, campaign)) == {}
    assert shares(add(client, campaign, D)) == {D: 100}
    act(client, campaign, "POST", "/push")
    assert in_keitaro(fake, campaign) == {D: 100}


def test_offer_can_be_added_to_stream_without_offers(client, fake, campaign):
    """Поток, который вёл по ссылке, показан как обычный поток, и в него можно добавить оффер."""
    state = fake.state.fake
    geo_id = next(key for key, stream in state.stored_streams.items() if stream["schema"] == "redirect")
    geo = {"id": campaign["id"], "stream": geo_id}

    before = next(s for s in client.get(f"/api/editor/campaigns/{campaign['id']}").json()["streams"] if s["id"] == geo_id)
    assert before["serves_offers"] is False
    assert before["offers"]["items"] == []

    assert shares(add(client, geo, A)) == {A: 100}
    act(client, geo, "POST", "/push")

    # Вместе с первым оффером поток переключается на офферы, иначе Keitaro их не покажет.
    assert state.puts[-1] == (geo_id, {"offers": [{"offer_id": A, "share": 100, "state": "active"}], "schema": "landings"})
    after = next(s for s in client.get(f"/api/editor/campaigns/{campaign['id']}").json()["streams"] if s["id"] == geo_id)
    assert after["serves_offers"] is True
    assert shares(after["offers"]) == {A: 100}


def test_usual_push_does_not_touch_stream_settings(client, fake, campaign):
    open_editor(client, campaign)
    add(client, campaign, D)

    act(client, campaign, "POST", "/push")

    assert set(fake.state.fake.puts[-1][1]) == {"offers"}


def test_nothing_to_push(client, fake, campaign):
    open_editor(client, campaign)

    response = client.post(f"/api/editor/streams/{campaign['stream']}/push")

    assert response.status_code == 422
    assert fake.state.fake.puts == []


def test_pinned_offer_loses_pin_when_removed(client, campaign):
    open_editor(client, campaign)
    act(client, campaign, "PUT", f"/offers/{A}/pin", json={"pinned": True})
    act(client, campaign, "DELETE", f"/offers/{A}")

    offers = act(client, campaign, "POST", f"/offers/{A}/restore")

    assert shares(offers) == {A: 33, B: 33, C: 34}
    assert next(item for item in offers["items"] if item["offer_id"] == A)["pinned"] is False


def test_unsent_changes_survive_reopening(client, fake, campaign):
    open_editor(client, campaign)
    add(client, campaign, D)

    offers = open_editor(client, campaign)  # закрыли вкладку и открыли снова

    assert shares(offers) == {A: 25, B: 25, C: 25, D: 25}
    assert offers["unsent"] is True
    assert fake.state.fake.puts == []


def test_editor_shows_all_streams_of_campaign(client, campaign):
    body = client.get(f"/api/editor/campaigns/{campaign['id']}").json()

    geo, offers = body["streams"]
    assert body["campaign"]["name"] == "campaign 2"
    assert body["campaign"]["url"].startswith("https://kt-emulator.test/")
    # Поток без офферов показан просто как поток: ни фильтров, ни адреса редиректа редактор не разбирает.
    assert set(geo) == {"id", "name", "position", "state", "serves_offers", "offers"}
    assert geo["name"] == "Гео AU" and geo["serves_offers"] is False
    assert geo["offers"]["items"] == []
    assert offers["serves_offers"] is True
    assert offers["offers"]["total"] == 100


def test_names_of_deleted_offers_are_still_shown(client, fake, campaign):
    fake.state.fake.set_offers(campaign["stream"], [{"offer_id": 18099, "share": 100}])

    offers = open_editor(client, campaign)

    assert offers["items"][0]["name"] == "18099 Старый оффер"


def test_unknown_campaign(client):
    response = client.get("/api/editor/campaigns/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Такой кампании нет в Keitaro."


def test_campaign_list_comes_from_keitaro(client, with_defaults):
    for name in ("первая", "вторая", "третья"):
        client.post("/api/campaigns", json={"name": name, "countries": ["MX"], "offer_id": A})

    page = client.get("/api/editor/campaigns", params={"limit": 2}).json()
    rest = client.get("/api/editor/campaigns", params={"limit": 2, "offset": 2}).json()

    assert [item["name"] for item in page["items"]] == ["третья", "вторая"]
    assert page["has_more"] is True
    assert [item["name"] for item in rest["items"]] == ["первая"]
    assert rest["has_more"] is False
    assert page["items"][0]["admin_url"].endswith(f"/campaign.editor/{page['items'][0]['id']}")
