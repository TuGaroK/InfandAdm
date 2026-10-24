import importlib
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

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


def test_subject_catalog_lists_exactly_three_supported_subjects():
    with TestClient(app_final.app) as client:
        response = client.get("/subjects")

    assert response.status_code == 200
    assert response.json() == {
        "subjects": [
            {
                "id": "discrete",
                "name": "Дискретные и непрерывные структуры",
            },
            {"id": "python", "name": "Программирование на Python"},
            {
                "id": "infrastructure",
                "name": "Инфраструктура и администрирование",
            },
        ]
    }


@pytest.mark.parametrize(
    ("subject_id", "component_ids", "labels", "weights", "rounding_policy"),
    [
        (
            "discrete",
            ["hw1", "hw2", "test1", "test2", "exam", "participation"],
            [
                "ДЗ №1",
                "ДЗ №2",
                "Контрольная №1",
                "Контрольная №2",
                "Экзамен",
                "Работа на занятиях",
            ],
            [0.2, 0.2, 0.1, 0.1, 0.4, 0.1],
            "unknown",
        ),
        (
            "python",
            ["homework_avg", "mini_tests_avg", "independent_avg", "exam"],
            [
                "Средняя оценка за домашние задания",
                "Средняя оценка за мини-тесты",
                "Средняя оценка за самостоятельные работы",
                "Экзамен",
            ],
            [0.1, 0.2, 0.2, 0.5],
            "half_up",
        ),
        ("infrastructure", ["project"], ["Итоговый проект"], [1.0], "half_up"),
    ],
)
def test_subject_detail_exposes_components_and_rules(
    subject_id, component_ids, labels, weights, rounding_policy
):
    with TestClient(app_final.app) as client:
        response = client.get(f"/subjects/{subject_id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == subject_id
    assert [component["id"] for component in detail["components"]] == component_ids
    assert [component["label"] for component in detail["components"]] == labels
    assert [component["weight"] for component in detail["components"]] == weights
    assert detail["grade_min"] == 0
    assert detail["grade_max"] == 10
    assert detail["score_cap"] == 10
    assert detail["rounding_policy"] == rounding_policy
    assert detail["rounding_note"]
    assert detail["notes"]


def test_subject_formulas_match_catalog_weights():
    expected_formulas = {
        "discrete": (
            "S = 0.2*hw1 + 0.2*hw2 + 0.1*test1 + 0.1*test2 + "
            "0.4*exam + 0.1*participation; score = min(S, 10)."
        ),
        "python": (
            "S = 0.1*homework_avg + 0.2*mini_tests_avg + "
            "0.2*independent_avg + 0.5*exam; score = min(S, 10)."
        ),
        "infrastructure": "S = project; score = min(S, 10).",
    }

    with TestClient(app_final.app) as client:
        details = {
            subject_id: client.get(f"/subjects/{subject_id}").json()
            for subject_id in expected_formulas
        }

    assert {
        subject_id: detail["formula"] for subject_id, detail in details.items()
    } == expected_formulas
    assert sum(
        Decimal(str(component["weight"]))
        for component in details["discrete"]["components"]
    ) == Decimal("1.1")


def test_unknown_subject_returns_404():
    with TestClient(app_final.app) as client:
        response = client.get("/subjects/not-a-subject")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Предмет с идентификатором 'not-a-subject' не найден."
    }
