"""Общая подготовка тестов: своя база в памяти и игрушечный Keitaro вместо настоящего.

Тесты никогда не ходят в сеть и не трогают файл .env.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.config import Settings, get_settings
from app.db import Base, get_db
from app.keitaro import KeitaroClient, get_keitaro
from app.main import app
from tests.fake_keitaro import API_KEY, make_fake_keitaro

KEITARO_URL = "https://tracker.test"


@pytest.fixture
def fake():
    """Игрушечный Keitaro. Через fake.state.fake видно, что ему прислали."""
    return make_fake_keitaro()


@pytest.fixture
def keitaro(fake):
    return KeitaroClient(KEITARO_URL, API_KEY, http=TestClient(fake, base_url=KEITARO_URL))


@pytest.fixture
def client(keitaro):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with session_factory() as session:
            yield session

    settings = Settings(_env_file=None, keitaro_url=KEITARO_URL, keitaro_api_key=API_KEY)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_keitaro] = lambda: keitaro
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture
def with_defaults(client):
    """Выбирает домен, группу и источник: без них кампанию создать нельзя."""
    response = client.put("/api/defaults", json={"domain_id": 1813, "group_id": 10332, "traffic_source_id": 836})
    assert response.status_code == 200
    return response.json()
