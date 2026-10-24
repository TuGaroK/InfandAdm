"""Рабочая основа сервиса расчёта накопленной оценки."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException


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
