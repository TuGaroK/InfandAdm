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


def test_python_full_calculation_returns_contributions_and_json_numbers():
    request_body = {
        "grades": {
            "homework_avg": 6.5,
            "mini_tests_avg": 8.5,
            "independent_avg": 7,
            "exam": 8,
        }
    }

    with TestClient(app_final.app) as client:
        response = client.post("/subjects/python/calculate", json=request_body)

    assert response.status_code == 200
    assert response.json() == {
        "subject_id": "python",
        "subject_name": "Программирование на Python",
        "raw_score": 7.75,
        "score": 7.75,
        "score_cap": 10,
        "is_complete": True,
        "missing_components": [],
        "rounding_policy": "half_up",
        "rounded_grade": 8,
        "contributions": [
            {
                "id": "homework_avg",
                "label": "Средняя оценка за домашние задания",
                "weight": 0.1,
                "grade": 6.5,
                "contribution": 0.65,
            },
            {
                "id": "mini_tests_avg",
                "label": "Средняя оценка за мини-тесты",
                "weight": 0.2,
                "grade": 8.5,
                "contribution": 1.7,
            },
            {
                "id": "independent_avg",
                "label": "Средняя оценка за самостоятельные работы",
                "weight": 0.2,
                "grade": 7,
                "contribution": 1.4,
            },
            {
                "id": "exam",
                "label": "Экзамен",
                "weight": 0.5,
                "grade": 8,
                "contribution": 4,
            },
        ],
        "message": "Полный расчёт выполнен: накопленная оценка — 7.75.",
    }
    assert isinstance(response.json()["score"], float)
    assert all(
        isinstance(item["contribution"], int | float)
        for item in response.json()["contributions"]
    )


@pytest.mark.parametrize(
    ("subject_id", "grades", "raw_score", "score", "rounded_grade"),
    [
        (
            "discrete",
            {
                "hw1": 6.5,
                "hw2": 8.5,
                "test1": 7,
                "test2": 8,
                "exam": 9,
                "participation": 10,
            },
            9.1,
            9.1,
            None,
        ),
        (
            "discrete",
            {
                "hw1": 10,
                "hw2": 10,
                "test1": 10,
                "test2": 10,
                "exam": 10,
                "participation": 10,
            },
            11,
            10,
            None,
        ),
        (
            "python",
            {
                "homework_avg": 4.5,
                "mini_tests_avg": 4.5,
                "independent_avg": 4.5,
                "exam": 4.5,
            },
            4.5,
            4.5,
            5,
        ),
        ("infrastructure", {"project": 8.5}, 8.5, 8.5, 9),
    ],
)
def test_full_calculation_examples(
    subject_id, grades, raw_score, score, rounded_grade
):
    with TestClient(app_final.app) as client:
        response = client.post(
            f"/subjects/{subject_id}/calculate",
            json={"grades": grades},
        )

    assert response.status_code == 200
    result = response.json()
    assert result["raw_score"] == raw_score
    assert result["score"] == score
    assert result["rounded_grade"] == rounded_grade
    assert result["is_complete"] is True
    assert result["missing_components"] == []


def test_calculation_for_unknown_subject_returns_404():
    with TestClient(app_final.app) as client:
        response = client.post(
            "/subjects/not-a-subject/calculate",
            json={"grades": {"project": 8.5}},
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Предмет с идентификатором 'not-a-subject' не найден."
    }


def test_partial_discrete_calculation_keeps_missing_components():
    with TestClient(app_final.app) as client:
        response = client.post(
            "/subjects/discrete/calculate",
            json={"grades": {"hw1": 6.5, "hw2": 8.5}},
        )

    assert response.status_code == 200
    result = response.json()
    assert result["raw_score"] == 3
    assert result["score"] == 3
    assert result["is_complete"] is False
    assert result["missing_components"] == [
        "test1",
        "test2",
        "exam",
        "participation",
    ]
    assert result["rounding_policy"] == "unknown"
    assert result["rounded_grade"] is None
    assert result["message"] == (
        "Неполный расчёт: учтён только вклад известных оценок — 3."
    )
    assert result["contributions"][0]["contribution"] == 1.3
    assert result["contributions"][1]["contribution"] == 1.7
    assert all(
        contribution["grade"] is None
        and contribution["contribution"] is None
        for contribution in result["contributions"][2:]
    )


def test_missing_key_and_null_have_the_same_meaning():
    with TestClient(app_final.app) as client:
        omitted_response = client.post(
            "/subjects/python/calculate",
            json={"grades": {"homework_avg": 6.5}},
        )
        null_response = client.post(
            "/subjects/python/calculate",
            json={
                "grades": {
                    "homework_avg": 6.5,
                    "mini_tests_avg": None,
                    "independent_avg": None,
                    "exam": None,
                }
            },
        )

    assert omitted_response.status_code == 200
    assert null_response.status_code == 200
    assert omitted_response.json() == null_response.json()
    assert omitted_response.json()["score"] == 0.65
    assert omitted_response.json()["rounded_grade"] is None


def test_zero_is_a_known_grade_in_partial_calculation():
    with TestClient(app_final.app) as client:
        response = client.post(
            "/subjects/discrete/calculate",
            json={"grades": {"hw1": 0}},
        )

    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 0
    assert result["is_complete"] is False
    assert result["contributions"][0]["grade"] == 0
    assert result["contributions"][0]["contribution"] == 0


@pytest.mark.parametrize(
    "grades",
    [
        {},
        {"hw1": None},
        {
            "hw1": None,
            "hw2": None,
            "test1": None,
            "test2": None,
            "exam": None,
            "participation": None,
        },
    ],
)
def test_calculation_rejects_requests_without_known_grades(grades):
    with TestClient(app_final.app) as client:
        response = client.post(
            "/subjects/discrete/calculate",
            json={"grades": grades},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "loc": ["body", "grades"],
            "type": "no_known_grades",
            "msg": (
                "Нечего рассчитывать: укажите хотя бы одну известную оценку."
            ),
        }
    ]


@pytest.mark.parametrize(
    ("subject_id", "component_id", "grade", "error_type", "message"),
    [
        (
            "infrastructure",
            "project",
            10.5,
            "grade_too_high",
            "Вы непризнанный гений или просто ошиблись числом?",
        ),
        (
            "python",
            "exam",
            -0.5,
            "grade_too_low",
            "Ничего страшного, Цезарь тоже не сразу стал салатом.",
        ),
    ],
)
def test_grade_range_errors_have_exact_messages_and_locations(
    subject_id, component_id, grade, error_type, message
):
    with TestClient(app_final.app) as client:
        response = client.post(
            f"/subjects/{subject_id}/calculate",
            json={"grades": {component_id: grade}},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "loc": ["body", "grades", component_id],
            "type": error_type,
            "msg": message,
            "hint": "Оценка должна быть числом от 0 до 10 включительно.",
        }
    ]


@pytest.mark.parametrize("grade", [True, "6.5", [], {}])
def test_calculation_rejects_non_numeric_grades(grade):
    with TestClient(app_final.app) as client:
        response = client.post(
            "/subjects/infrastructure/calculate",
            json={"grades": {"project": grade}},
        )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "grades", "project"]
    assert error["type"] == "grade_type"


@pytest.mark.parametrize("number_literal", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_calculation_rejects_non_finite_numbers(number_literal):
    body = f'{{"grades":{{"project":{number_literal}}}}}'

    with TestClient(app_final.app) as client:
        response = client.post(
            "/subjects/infrastructure/calculate",
            content=body,
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "grades", "project"]
    assert error["type"] == "grade_not_finite"


def test_unknown_component_and_extra_request_field_are_rejected():
    with TestClient(app_final.app) as client:
        component_response = client.post(
            "/subjects/infrastructure/calculate",
            json={"grades": {"projcet": 8.5}},
        )
        extra_field_response = client.post(
            "/subjects/infrastructure/calculate",
            json={"grades": {"project": 8.5}, "comment": "лишнее поле"},
        )

    assert component_response.status_code == 422
    assert component_response.json()["detail"][0] == {
        "loc": ["body", "grades", "projcet"],
        "type": "unknown_component",
        "msg": "Компонент 'projcet' не найден у этого предмета.",
    }
    assert extra_field_response.status_code == 422
    assert extra_field_response.json()["detail"][0]["loc"] == [
        "body",
        "comment",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"grades": None},
        {"grades": []},
        {"grades": "project=8.5"},
        {"grades": 8.5},
    ],
)
def test_grades_must_be_an_object(body):
    with TestClient(app_final.app) as client:
        response = client.post(
            "/subjects/infrastructure/calculate",
            json=body,
        )

    assert response.status_code == 422
    assert response.json()["detail"]
    assert response.json()["detail"][0]["loc"][0] == "body"


@pytest.mark.parametrize(
    "body",
    [
        '{"grades":NaN}',
        '{"grades":{"project":8.5},"comment":NaN}',
    ],
)
def test_non_finite_validation_errors_never_become_server_errors(body):
    with TestClient(app_final.app, raise_server_exceptions=False) as client:
        response = client.post(
            "/subjects/infrastructure/calculate",
            content=body,
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_repeated_calculations_are_independent_and_do_not_change_subjects():
    with TestClient(app_final.app) as client:
        subject_before = client.get("/subjects/python").json()
        first = client.post(
            "/subjects/python/calculate",
            json={"grades": {"homework_avg": 6.5}},
        )
        second = client.post(
            "/subjects/python/calculate",
            json={
                "grades": {
                    "homework_avg": 4.5,
                    "mini_tests_avg": 4.5,
                    "independent_avg": 4.5,
                    "exam": 4.5,
                }
            },
        )
        subject_after = client.get("/subjects/python").json()

    assert first.json()["score"] == 0.65
    assert second.json()["score"] == 4.5
    assert subject_after == subject_before


def test_openapi_contains_full_and_partial_request_examples():
    with TestClient(app_final.app) as client:
        response = client.get("/openapi.json")

    examples = response.json()["components"]["schemas"][
        "CalculationRequest"
    ]["examples"]
    assert len(examples) == 2
    assert examples[0]["grades"]["exam"] == 8
    assert examples[1]["grades"] == {"homework_avg": 6.5}


def test_obsolete_classroom_routes_are_removed():
    with TestClient(app_final.app) as client:
        openapi = client.get("/openapi.json").json()

    assert "/hello" not in openapi["paths"]
    assert "/info" not in openapi["paths"]


def test_calculation_logs_outcome_without_grade_values(monkeypatch):
    messages = []

    def capture_log(message, *arguments):
        messages.append(message % arguments)

    with TestClient(app_final.app) as client:
        monkeypatch.setattr(app_final.logger, "info", capture_log)
        response = client.post(
            "/subjects/infrastructure/calculate",
            json={"grades": {"project": 8.5}},
        )

    assert response.status_code == 200
    calculation_log = next(
        message for message in messages if message.startswith("Расчёт выполнен:")
    )
    assert "subject=infrastructure" in calculation_log
    assert "complete=True" in calculation_log
    assert "8.5" not in calculation_log


def test_calculation_logs_error_without_invalid_grade(monkeypatch):
    messages = []

    def capture_log(message, *arguments):
        messages.append(message % arguments)

    with TestClient(app_final.app) as client:
        monkeypatch.setattr(app_final.logger, "warning", capture_log)
        response = client.post(
            "/subjects/infrastructure/calculate",
            json={"grades": {"project": 10.5}},
        )

    assert response.status_code == 422
    assert messages == [
        (
            "Ошибка расчёта: subject=infrastructure status=422 "
            "type=grade_too_high."
        )
    ]
    assert "10.5" not in messages[0]
