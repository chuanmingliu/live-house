from __future__ import annotations

from fastapi.testclient import TestClient


def test_fal_webhook_completion_is_idempotent(slow_mock_client: TestClient) -> None:
    client = slow_mock_client
    demo = client.post("/v1/demo/bootstrap").json()
    session_id = demo["session"]["id"]
    submitted = client.post(
        f"/v1/live-sessions/{session_id}/segments:generate",
        json={"prompt": "A product shot", "duration_ms": 5000},
    ).json()

    webhook = {
        "request_id": submitted["fal_request_id"],
        "gateway_request_id": submitted["fal_request_id"],
        "status": "OK",
        "payload": {"video": {"url": "https://cdn.example/generated.mp4"}},
    }
    first = client.post("/v1/webhooks/fal", json=webhook)
    second = client.post("/v1/webhooks/fal", json=webhook)

    assert first.status_code == 200
    assert first.json()["processed"] is True
    assert first.json()["segment"]["state"] == "READY"
    assert first.json()["segment"]["asset_url"] == "https://cdn.example/generated.mp4"

    assert second.status_code == 200
    assert second.json()["processed"] is False
    assert second.json()["segment"]["state"] == "READY"


def test_same_webhook_request_id_with_different_body_is_rejected(
    slow_mock_client: TestClient,
) -> None:
    client = slow_mock_client
    demo = client.post("/v1/demo/bootstrap").json()
    session_id = demo["session"]["id"]
    submitted = client.post(
        f"/v1/live-sessions/{session_id}/segments:generate",
        json={"prompt": "A product shot", "duration_ms": 5000},
    ).json()

    first = {
        "request_id": submitted["fal_request_id"],
        "status": "OK",
        "payload": {"video": {"url": "https://cdn.example/one.mp4"}},
    }
    altered = {
        "request_id": submitted["fal_request_id"],
        "status": "OK",
        "payload": {"video": {"url": "https://cdn.example/two.mp4"}},
    }
    assert client.post("/v1/webhooks/fal", json=first).status_code == 200
    response = client.post("/v1/webhooks/fal", json=altered)
    assert response.status_code == 409
