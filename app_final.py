"""FastAPI-сервис расчёта накопленной оценки."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
import json
import logging
import math
import os
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from calculator import calculate_subject


APP_NAME = os.getenv("APP_NAME", "Калькулятор накопа")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")


def _load_subjects() -> tuple[dict[str, object], ...]:
    data_path = Path(__file__).resolve().parent / "data" / "subjects.json"
    with data_path.open(encoding="utf-8") as data_file:
        data = json.load(data_file)

    return tuple(data["subjects"])


_SUBJECTS = _load_subjects()
_SUBJECTS_BY_ID = {subject["id"]: subject for subject in _SUBJECTS}

if len(_SUBJECTS_BY_ID) != len(_SUBJECTS):
    raise RuntimeError("Идентификаторы предметов в каталоге должны быть уникальны.")


def _get_subject(subject_id: str) -> dict[str, object]:
    subject = _SUBJECTS_BY_ID.get(subject_id)
    if subject is None:
        raise HTTPException(
            status_code=404,
            detail=f"Предмет с идентификатором '{subject_id}' не найден.",
        )
    return subject


def _build_formula(subject: dict[str, object]) -> str:
    terms = []
    for component in subject["components"]:
        weight = str(component["weight"])
        if Decimal(weight) == Decimal("1"):
            terms.append(str(component["id"]))
        else:
            terms.append(f"{weight}*{component['id']}")

    expression = " + ".join(terms)
    return f"S = {expression}; score = min(S, {subject['score_cap']})."


def _subject_detail(subject: dict[str, object]) -> dict[str, object]:
    components = [
        {
            "id": component["id"],
            "label": component["label"],
            "weight": float(Decimal(str(component["weight"]))),
        }
        for component in subject["components"]
    ]
    return {
        "id": subject["id"],
        "name": subject["name"],
        "formula": _build_formula(subject),
        "components": components,
        "grade_min": subject["grade_min"],
        "grade_max": subject["grade_max"],
        "score_cap": subject["score_cap"],
        "rounding_policy": subject["rounding_policy"],
        "rounding_note": subject["rounding_note"],
        "notes": list(subject["notes"]),
    }


class CalculationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "grades": {
                        "homework_avg": 6.5,
                        "mini_tests_avg": 8.5,
                        "independent_avg": 7,
                        "exam": 8,
                    }
                },
                {
                    "grades": {
                        "homework_avg": 6.5,
                        "mini_tests_avg": None,
                    }
                },
            ]
        },
    )

    grades: dict[str, object | None]


_GRADE_HINT = "Оценка должна быть числом от 0 до 10 включительно."


def _grade_error(
    component_id: str,
    error_type: str,
    message: str,
) -> dict[str, object]:
    return {
        "loc": ["body", "grades", component_id],
        "type": error_type,
        "msg": message,
        "hint": _GRADE_HINT,
    }


def _validate_grades(
    subject: dict[str, object],
    grades: dict[str, object | None],
) -> dict[str, int | float | None]:
    component_ids = [
        str(component["id"]) for component in subject["components"]
    ]
    grade_min = int(subject["grade_min"])
    grade_max = int(subject["grade_max"])
    errors = []
    validated_grades: dict[str, int | float | None] = {}

    for component_id, grade in grades.items():
        if component_id not in component_ids:
            errors.append(
                {
                    "loc": ["body", "grades", component_id],
                    "type": "unknown_component",
                    "msg": (
                        f"Компонент '{component_id}' не найден у этого предмета."
                    ),
                }
            )
            continue

        if grade is None:
            validated_grades[component_id] = None
            continue

        if type(grade) not in (int, float):
            errors.append(
                _grade_error(
                    component_id,
                    "grade_type",
                    "Оценка должна быть конечным JSON-числом или null.",
                )
            )
            continue

        numeric_grade = cast(int | float, grade)
        if isinstance(numeric_grade, float) and not math.isfinite(numeric_grade):
            errors.append(
                _grade_error(
                    component_id,
                    "grade_not_finite",
                    "Оценка должна быть конечным числом.",
                )
            )
            continue

        if numeric_grade > grade_max:
            errors.append(
                _grade_error(
                    component_id,
                    "grade_too_high",
                    "Вы непризнанный гений или просто ошиблись числом?",
                )
            )
            continue

        if numeric_grade < grade_min:
            errors.append(
                _grade_error(
                    component_id,
                    "grade_too_low",
                    "Ничего страшного, Цезарь тоже не сразу стал салатом.",
                )
            )
            continue

        validated_grades[component_id] = numeric_grade

    if errors:
        raise HTTPException(status_code=422, detail=errors)

    if not any(grade is not None for grade in validated_grades.values()):
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": ["body", "grades"],
                    "type": "no_known_grades",
                    "msg": (
                        "Нечего рассчитывать: укажите хотя бы одну "
                        "известную оценку."
                    ),
                }
            ],
        )

    return validated_grades


def _safe_request_errors(
    exception: RequestValidationError,
) -> list[dict[str, object]]:
    errors = []
    for error in exception.errors():
        location = [
            part if isinstance(part, (str, int)) else str(part)
            for part in error.get("loc", ())
        ]
        errors.append(
            {
                "loc": location,
                "type": str(error.get("type", "validation_error")),
                "msg": str(error.get("msg", "Некорректный запрос.")),
            }
        )
    return errors


def _optional_json_number(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    return _json_number(value)


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _calculation_response(result: dict[str, object]) -> dict[str, object]:
    contributions = [
        {
            "id": contribution["id"],
            "label": contribution["label"],
            "weight": _json_number(contribution["weight"]),
            "grade": _optional_json_number(contribution["grade"]),
            "contribution": _optional_json_number(
                contribution["contribution"]
            ),
        }
        for contribution in result["contributions"]
    ]
    return {
        "subject_id": result["subject_id"],
        "subject_name": result["subject_name"],
        "raw_score": _json_number(result["raw_score"]),
        "score": _json_number(result["score"]),
        "score_cap": _json_number(result["score_cap"]),
        "is_complete": result["is_complete"],
        "missing_components": result["missing_components"],
        "rounding_policy": result["rounding_policy"],
        "rounded_grade": result["rounded_grade"],
        "contributions": contributions,
        "message": result["message"],
    }


_requested_log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
_configured_log_level = getattr(logging, _requested_log_level, None)
if not isinstance(_configured_log_level, int):
    LOG_LEVEL = "INFO"
    _configured_log_level = logging.INFO
else:
    LOG_LEVEL = _requested_log_level

logger = logging.getLogger("grade_calculator")
logger.setLevel(_configured_log_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.addHandler(handler)
logger.propagate = False

if LOG_LEVEL != _requested_log_level:
    logger.warning(
        "Неизвестный LOG_LEVEL=%r; используется INFO.", _requested_log_level
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Запуск сервиса «%s» версии %s (LOG_LEVEL=%s).",
        APP_NAME,
        APP_VERSION,
        LOG_LEVEL,
    )
    yield
    logger.info("Остановка сервиса «%s».", APP_NAME)


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def request_validation_error(
    request: Request,
    exception: RequestValidationError,
):
    errors = _safe_request_errors(exception)
    error_types = ",".join(str(error["type"]) for error in errors)
    logger.warning(
        "Ошибка валидации запроса: path=%s types=%s.",
        request.url.path,
        error_types,
    )
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/")
def root():
    return {
        "message": f"Сервис «{APP_NAME}» работает",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": APP_VERSION}


@app.get("/subjects")
def list_subjects():
    return {
        "subjects": [
            {"id": subject["id"], "name": subject["name"]}
            for subject in _SUBJECTS
        ]
    }


@app.get("/subjects/{subject_id}")
def subject_detail(subject_id: str):
    return _subject_detail(_get_subject(subject_id))


@app.post("/subjects/{subject_id}/calculate")
def calculate(subject_id: str, request: CalculationRequest):
    try:
        subject = _get_subject(subject_id)
        grades = _validate_grades(subject, request.grades)
        result = calculate_subject(subject, grades)
    except HTTPException as error:
        error_type = "subject_not_found"
        if isinstance(error.detail, list) and error.detail:
            error_type = str(error.detail[0].get("type", "calculation_error"))
        logger.warning(
            "Ошибка расчёта: subject=%s status=%s type=%s.",
            subject_id,
            error.status_code,
            error_type,
        )
        raise

    logger.info(
        "Расчёт выполнен: subject=%s complete=%s missing=%s.",
        subject_id,
        result["is_complete"],
        len(result["missing_components"]),
    )
    return _calculation_response(result)
