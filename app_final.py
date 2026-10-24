"""Рабочая основа сервиса расчёта накопленной оценки."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI


APP_NAME = os.getenv("APP_NAME", "Калькулятор накопа")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

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
