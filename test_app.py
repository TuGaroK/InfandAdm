import importlib

from fastapi.testclient import TestClient

import app_final


def test_health():
    with TestClient(app_final.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_uses_default(monkeypatch):
    with monkeypatch.context() as environment:
        environment.delenv("APP_VERSION", raising=False)
        configured_app = importlib.reload(app_final)

        with TestClient(configured_app.app) as client:
            response = client.get("/version")

        assert response.status_code == 200
        assert response.json() == {"version": "0.1.0"}
        assert configured_app.app.version == "0.1.0"

    importlib.reload(app_final)


def test_app_name_environment_setting(monkeypatch):
    with monkeypatch.context() as environment:
        environment.setenv("APP_NAME", "Тестовый калькулятор")
        configured_app = importlib.reload(app_final)

        with TestClient(configured_app.app) as client:
            response = client.get("/openapi.json")

        assert response.status_code == 200
        assert response.json()["info"]["title"] == "Тестовый калькулятор"

    importlib.reload(app_final)
