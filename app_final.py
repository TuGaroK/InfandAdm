"""Рабочая основа сервиса расчёта накопленной оценки."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
import json
import logging
import math
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt

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
    model_config = ConfigDict(extra="forbid")

    grades: dict[str, StrictInt | StrictFloat]


def _validate_complete_grades(
    subject: dict[str, object],
    grades: dict[str, int | float],
) -> None:
    component_ids = [component["id"] for component in subject["components"]]
    unknown = [
        component_id
        for component_id in grades
        if component_id not in component_ids
    ]
    missing = [
        component_id
        for component_id in component_ids
        if component_id not in grades
    ]

    if unknown or missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Для расчёта нужны оценки всех компонентов предмета.",
                "missing_components": missing,
                "unknown_components": unknown,
            },
        )

    grade_min = subject["grade_min"]
    grade_max = subject["grade_max"]
    for component_id, grade in grades.items():
        if isinstance(grade, float) and not math.isfinite(grade):
            raise HTTPException(
                status_code=422,
                detail=f"Оценка {component_id} должна быть конечным числом.",
            )
        if grade < grade_min or grade > grade_max:
            raise HTTPException(
                status_code=422,
                detail=f"Оценка {component_id} должна быть от 0 до 10.",
            )


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
            "grade": _json_number(contribution["grade"]),
            "contribution": _json_number(contribution["contribution"]),
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
    subject = _get_subject(subject_id)
    grades = request.grades
    _validate_complete_grades(subject, grades)
    return _calculation_response(calculate_subject(subject, grades))


@app.get("/hello")
def hello(name: str = "студент"):
    return {"message": f"Привет, {name}!"}


@app.get("/info")
def info():
    app_author = os.getenv("APP_AUTHOR", "Не указан")

    return {
        "app_name": APP_NAME,
        "author": app_author,
    }
