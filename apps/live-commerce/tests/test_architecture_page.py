from __future__ import annotations

from fastapi.testclient import TestClient


def test_interactive_architecture_page_is_served(client: TestClient) -> None:
    response = client.get("/architecture")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AI-Native Live-Commerce Architecture" in response.text
    assert "window.__ARCH_DEMO_READY__" in response.text
    assert 'data-mode-button="production"' in response.text
    assert 'data-flow="ai"' in response.text
