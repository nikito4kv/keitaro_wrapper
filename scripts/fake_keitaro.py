"""A tiny stand-in for the Keitaro Admin API, so the whole app can be demoed without a real tracker.

It implements only the endpoints the app calls, keeps everything in memory and is pre-filled with
made-up data (example.com domains, fictional offers and campaigns). Restart it to reset the data.

    python scripts/fake_keitaro.py            # listens on http://127.0.0.1:8099

Then point the app at it (in .env or in the environment):

    KEITARO_URL=http://127.0.0.1:8099
    KEITARO_API_KEY=demo-key
"""

from __future__ import annotations

import argparse
from itertools import count

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

API_KEY = "demo-key"

OFFERS = [
    {"id": 1001, "name": "1001 Nimbus VPN [APP-DE] [trial] DemoNet v2", "country": ["DE"]},
    {"id": 1002, "name": "1002 Pixel Quest [GAME-US] [install] SampleAds v1", "country": ["US"]},
    {"id": 1003, "name": "1003 Coffee Club Box [FOOD-FR] [sweeps] DemoNet v1", "country": ["FR"]},
    {"id": 1004, "name": "1004 Fitly Tracker [APP-ES] [trial] SampleAds v3", "country": ["ES"]},
    {"id": 1005, "name": "1005 Lumen Desk Lamp [SHOP-PL] [cod] DemoNet v1", "country": ["PL"]},
    {"id": 1006, "name": "1006 Trail Runner Shoes [SHOP-MX] [cod] SampleAds v2", "country": ["MX"]},
    {"id": 1007, "name": "1007 Budget Planner [APP-AU] [trial] DemoNet v4", "country": ["AU"]},
    {"id": 1008, "name": "1008 Language Buddy [EDU-RO] [trial] SampleAds v1", "country": ["RO"]},
    {"id": 1009, "name": "1009 Retired Promo", "country": [], "state": "deleted"},
]
DOMAINS = [
    {"id": 1, "name": "go.example.com", "is_ssl": True, "state": "active"},
    {"id": 2, "name": "link.example.com", "is_ssl": True, "state": "active"},
]
GROUPS = [
    {"id": 1, "name": "Demo group", "type": "campaigns"},
    {"id": 2, "name": "Spring tests", "type": "campaigns"},
]
SOURCES = [
    {"id": 1, "name": "Demo Traffic Source", "state": "active"},
    {"id": 2, "name": "Sample Push Network", "state": "active"},
]

DEFAULT_DOMAIN = "https://go.example.com"


def make_app() -> FastAPI:
    app = FastAPI(title="Fake Keitaro (demo)")
    campaigns: dict[int, dict] = {}
    streams: dict[int, dict] = {}
    campaign_ids = count(31)
    stream_ids = count(601)
    row_ids = count(9001)

    def offer_rows(stream_id: int, offers: list[dict]) -> list[dict]:
        kept = {row["offer_id"]: row["id"] for row in streams.get(stream_id, {}).get("offers", [])}
        return [
            {
                "id": kept.get(offer["offer_id"]) or next(row_ids),
                "stream_id": stream_id,
                "offer_id": offer["offer_id"],
                "share": offer["share"],
                "state": offer.get("state", "active"),
            }
            for offer in offers
        ]

    def add_campaign(body: dict, created_at: str) -> dict:
        campaign_id = next(campaign_ids)
        campaigns[campaign_id] = {"id": campaign_id, "created_at": created_at, "domain": DEFAULT_DOMAIN, **body}
        return campaigns[campaign_id]

    def add_stream(body: dict) -> dict:
        stream_id = next(stream_ids)
        stream = {
            "id": stream_id,
            "campaign_id": body["campaign_id"],
            "name": body["name"],
            "type": body.get("type", "regular"),
            "position": body.get("position", 1),
            "state": body.get("state", "active"),
            "schema": body.get("schema", "landings"),
            "action_type": body.get("action_type"),
            "action_payload": body.get("action_payload"),
            "filters": body.get("filters", []),
            "offers": [],
        }
        streams[stream_id] = stream
        stream["offers"] = offer_rows(stream_id, body.get("offers", []))
        return stream

    def seed() -> None:
        def demo(name: str, alias: str, created_at: str, countries: list[str], offers: list[tuple[int, int]]) -> None:
            campaign = add_campaign({"name": name, "alias": alias, "state": "active"}, created_at)
            add_stream(
                {
                    "campaign_id": campaign["id"],
                    "name": "Гео " + ", ".join(countries),
                    "position": 1,
                    "schema": "redirect",
                    "action_type": "http",
                    "action_payload": "https://google.com",
                    "filters": [{"name": "country", "mode": "accept", "payload": countries}],
                }
            )
            add_stream(
                {
                    "campaign_id": campaign["id"],
                    "name": "Офферы",
                    "type": "default",
                    "position": 2,
                    "schema": "landings",
                    "offers": [{"offer_id": offer_id, "share": share} for offer_id, share in offers],
                }
            )

        demo("spring_vpn_de", "Xk3pQ9aB", "2026-11-18 09:12:40", ["DE", "AT"], [(1001, 50), (1002, 50)])
        demo("winter_fitness_es", "m7TzR2vC", "2026-11-20 14:03:11", ["ES", "MX"], [(1004, 33), (1006, 33), (1007, 34)])
        demo("coffee_box_fr", "Hq8LwN5d", "2026-11-22 11:47:25", ["FR", "BE", "CH"], [(1003, 100)])

    seed()

    @app.middleware("http")
    async def check_key(request: Request, call_next):
        if request.headers.get("Api-Key") != API_KEY:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

    def not_found() -> JSONResponse:
        return JSONResponse({"error": "Entity not found"}, status_code=404)

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

    @app.get("/admin_api/v1/campaigns")
    def list_campaigns(offset: int = 0, limit: int = 100):
        newest_first = sorted(campaigns.values(), key=lambda campaign: campaign["id"], reverse=True)
        return newest_first[offset : offset + limit]

    @app.get("/admin_api/v1/campaigns/{campaign_id}")
    def get_campaign(campaign_id: int):
        return campaigns.get(campaign_id) or not_found()

    @app.get("/admin_api/v1/campaigns/{campaign_id}/streams")
    def get_campaign_streams(campaign_id: int):
        if campaign_id not in campaigns:
            return not_found()
        found = [stream for stream in streams.values() if stream["campaign_id"] == campaign_id]
        return sorted(found, key=lambda stream: stream["position"])

    @app.post("/admin_api/v1/campaigns")
    async def create_campaign(request: Request):
        body = await request.json()
        if any(campaign["name"] == body["name"] for campaign in campaigns.values()):
            return JSONResponse({"name": ["Campaign with this name already exists"]}, status_code=406)
        domain = next((d for d in DOMAINS if d["id"] == body.get("domain_id")), None)
        campaign = add_campaign(body, "2026-11-26 10:30:00")
        if domain:
            campaign["domain"] = f"https://{domain['name']}"
        return campaign

    @app.delete("/admin_api/v1/campaigns/{campaign_id}")
    def delete_campaign(campaign_id: int):
        if campaigns.pop(campaign_id, None) is None:
            return not_found()
        for stream_id in [sid for sid, stream in streams.items() if stream["campaign_id"] == campaign_id]:
            del streams[stream_id]
        return {"success": True}

    @app.post("/admin_api/v1/streams")
    async def create_stream(request: Request):
        body = await request.json()
        if body["campaign_id"] not in campaigns:
            return not_found()
        return add_stream(body)

    @app.get("/admin_api/v1/streams/{stream_id}")
    def get_stream(stream_id: int):
        return streams.get(stream_id) or not_found()

    @app.put("/admin_api/v1/streams/{stream_id}")
    async def update_stream(stream_id: int, request: Request):
        body = await request.json()
        stream = streams.get(stream_id)
        if stream is None:
            return not_found()
        if "offers" in body:
            stream["offers"] = offer_rows(stream_id, body["offers"])
        if "schema" in body:
            stream["schema"] = body["schema"]
        return stream

    return app


app = make_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    print(f"Fake Keitaro on http://127.0.0.1:{args.port}  (Api-Key: {API_KEY})")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
