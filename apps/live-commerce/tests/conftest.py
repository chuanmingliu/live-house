from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from livecommerce.config import Settings
from livecommerce.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        app_env="test",
        database_path=str(tmp_path / "live-commerce.db"),
        public_base_url="http://testserver",
        cors_origins="http://testserver",
        fal_mode="mock",
        fal_verify_webhooks=False,
        mock_generation_delay_seconds=0.02,
        auto_seed_products=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def demo(client: TestClient) -> dict:
    response = client.post("/v1/demo/bootstrap")
    assert response.status_code == 200
    return response.json()

@pytest.fixture
def slow_mock_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        app_env="test",
        database_path=str(tmp_path / "slow-live-commerce.db"),
        public_base_url="http://testserver",
        cors_origins="http://testserver",
        fal_mode="mock",
        fal_verify_webhooks=False,
        mock_generation_delay_seconds=60,
        auto_seed_products=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def deadline_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        app_env="test",
        database_path=str(tmp_path / "deadline-live-commerce.db"),
        public_base_url="http://testserver",
        cors_origins="http://testserver",
        fal_mode="mock",
        fal_verify_webhooks=False,
        fal_job_deadline_seconds=1,
        mock_generation_delay_seconds=10,
        auto_seed_products=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
