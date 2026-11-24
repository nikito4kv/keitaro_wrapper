"""Игрушечный Keitaro для тестов: отвечает как Admin API в той части, которой пользуется приложение.

Запоминает всё, что ему прислали, чтобы тест мог проверить точное содержимое запросов.
"""

from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

API_KEY = "test-key"

OFFERS = [
    {"id": 18001, "name": "18001 Detoxin [HAIR-CL] [vsl es -] CPAHUB v2", "state": "active", "country": ["CL"]},
    {"id": 18002, "name": "18002 Fungiclean [PARASITE-TH] [spin th -] OFFERIA", "state": "active", "country": ["TH"]},
    {"id": 18003, "name": "18003 Slimora [DIET-CO] [article es -] LEADFOX v1", "state": "active", "country": ["CO"]},
    {"id": 18004, "name": "18004 Hepatix [PROSTATE-DE] [quiz de -] ADNOVA v3", "state": "active", "country": ["DE"]},
    {"id": 18005, "name": "18005 Cardiolux [HAIR-CO] [quiz es -] CPAHUB v3", "state": "active", "country": ["CO"]},
    {"id": 18008, "name": "18008 Detoxin [PROSTATE-IN] [article en -] OFFERIA v5", "state": "active", "country": ["IN"]},
    {"id": 18099, "name": "18099 Старый оффер", "state": "deleted", "country": []},
]
DOMAINS = [{"id": 1813, "name": "kt-emulator.test", "is_ssl": True, "state": "active"}]
GROUPS = [{"id": 10332, "name": "FORTESTS", "position": 0, "type": "campaigns"}]
SOURCES = [{"id": 836, "name": "FORTESTS", "state": "active"}]


def make_fake_keitaro() -> FastAPI:
    app = FastAPI()
    state = SimpleNamespace(
        campaigns={},  # id -> тело запроса на создание
        streams=[],  # тела запросов на создание потоков, по порядку
        deleted=[],  # номера удалённых кампаний
        fail_stream_number=None,  # какой по счёту поток отклонить (1 или 2)
        stream_attempts=0,
        stored_streams={},  # id -> поток, как его хранит трекер (с офферами)
        puts=[],  # (id потока, тело запроса) для каждой правки потока
        next_offer_row=900,
    )
    app.state.fake = state

    def offer_rows(stream_id: int, offers: list[dict]) -> list[dict]:
        """Строки офферов потока, как их отдаёт Keitaro: у каждой свой номер."""
        old = {row["offer_id"]: row["id"] for row in state.stored_streams.get(stream_id, {}).get("offers", [])}
        rows = []
        for offer in offers:
            row_id = old.get(offer["offer_id"])
            if row_id is None:
                state.next_offer_row += 1
                row_id = state.next_offer_row
            rows.append(
                {
                    "id": row_id,
                    "stream_id": stream_id,
                    "offer_id": offer["offer_id"],
                    "share": offer["share"],
                    "state": offer.get("state", "active"),
                }
            )
        return rows

    def set_offers(stream_id: int, offers: list[dict]) -> None:
        """Подмена состава потока «руками в Keitaro», в обход приложения."""
        state.stored_streams[stream_id]["offers"] = offer_rows(stream_id, offers)

    state.set_offers = set_offers

    @app.middleware("http")
    async def check_key(request: Request, call_next):
        if request.headers.get("Api-Key") != API_KEY:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/admin_api/v1/offers")
    def offers():
        return OFFERS

    @app.get("/admin_api/v1/domains")
    def domains():
        return DOMAINS

    @app.get("/admin_api/v1/groups")
    def groups(type: str):
        return [group for group in GROUPS if group["type"] == type]

    @app.get("/admin_api/v1/traffic_sources")
    def traffic_sources():
        return SOURCES

    def campaign_out(campaign_id: int) -> dict:
        return {
            "id": campaign_id,
            "state": "active",
            "created_at": "2026-11-24 10:18:03",
            "domain": "https://kt-emulator.test/",
            **state.campaigns[campaign_id],
        }

    @app.get("/admin_api/v1/campaigns")
    def list_campaigns(offset: int = 0, limit: int = 100):
        newest_first = sorted(state.campaigns, reverse=True)
        return [campaign_out(campaign_id) for campaign_id in newest_first[offset : offset + limit]]

    @app.get("/admin_api/v1/campaigns/{campaign_id}")
    def get_campaign(campaign_id: int):
        if campaign_id not in state.campaigns:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        return campaign_out(campaign_id)

    @app.get("/admin_api/v1/campaigns/{campaign_id}/streams")
    def get_campaign_streams(campaign_id: int):
        if campaign_id not in state.campaigns:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        streams = [stream for stream in state.stored_streams.values() if stream["campaign_id"] == campaign_id]
        return sorted(streams, key=lambda stream: stream["position"])

    @app.post("/admin_api/v1/campaigns")
    async def create_campaign(request: Request):
        body = await request.json()
        if any(campaign["name"] == body["name"] for campaign in state.campaigns.values()):
            return JSONResponse({"name": ["Campaign with this name already exists"]}, status_code=406)
        campaign_id = 100 + len(state.campaigns) + len(state.deleted)
        state.campaigns[campaign_id] = body
        return {"id": campaign_id, **body}

    @app.post("/admin_api/v1/streams")
    async def create_stream(request: Request):
        body = await request.json()
        state.stream_attempts += 1
        if state.fail_stream_number == state.stream_attempts:
            return JSONResponse({"error": "Stream rejected"}, status_code=400)
        if body["campaign_id"] not in state.campaigns:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        state.streams.append(body)
        stream_id = 500 + len(state.streams)
        state.stored_streams[stream_id] = {
            "id": stream_id,
            "campaign_id": body["campaign_id"],
            "name": body["name"],
            "type": body.get("type", "regular"),
            "position": body.get("position", len(state.streams)),
            "state": body.get("state", "active"),
            "schema": body.get("schema", "landings"),
            "action_type": body.get("action_type"),
            "action_payload": body.get("action_payload"),
            "filters": body.get("filters", []),
            "offers": [],
        }
        state.stored_streams[stream_id]["offers"] = offer_rows(stream_id, body.get("offers", []))
        return {**state.stored_streams[stream_id]}

    @app.put("/admin_api/v1/streams/{stream_id}")
    async def update_stream(stream_id: int, request: Request):
        body = await request.json()
        if stream_id not in state.stored_streams:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        state.puts.append((stream_id, body))
        if "offers" in body:
            state.stored_streams[stream_id]["offers"] = offer_rows(stream_id, body["offers"])
        return state.stored_streams[stream_id]

    @app.delete("/admin_api/v1/campaigns/{campaign_id}")
    def delete_campaign(campaign_id: int):
        if campaign_id not in state.campaigns:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        del state.campaigns[campaign_id]
        state.deleted.append(campaign_id)
        for stream_id in [key for key, stream in state.stored_streams.items() if stream["campaign_id"] == campaign_id]:
            del state.stored_streams[stream_id]
        return {"success": True}

    return app
