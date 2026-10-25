"""Расчёт накопленной оценки без зависимости от HTTP."""

from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _as_decimal(value: int | float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def calculate_subject(
    subject: Mapping[str, Any],
    grades: Mapping[str, int | float | Decimal | None],
) -> dict[str, Any]:
    """Рассчитать накоп по известным компонентам предмета."""

    raw_score = Decimal("0")
    contributions = []
    missing_components = []
    known_grades = 0

    for component in subject["components"]:
        component_id = component["id"]
        weight = Decimal(component["weight"])
        grade_value = grades.get(component_id)
        if grade_value is None:
            missing_components.append(component_id)
            contributions.append(
                {
                    "id": component_id,
                    "label": component["label"],
                    "weight": weight,
                    "grade": None,
                    "contribution": None,
                }
            )
            continue

        grade = _as_decimal(grade_value)
        contribution = grade * weight
        raw_score += contribution
        known_grades += 1
        contributions.append(
            {
                "id": component_id,
                "label": component["label"],
                "weight": weight,
                "grade": grade,
                "contribution": contribution,
            }
        )

    if known_grades == 0:
        raise ValueError("Для расчёта нужна хотя бы одна известная оценка.")

    score_cap = _as_decimal(subject["score_cap"])
    score = min(raw_score, score_cap)
    is_complete = not missing_components
    rounded_grade = None
    if is_complete and subject["rounding_policy"] == "half_up":
        rounded_grade = int(
            score.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

    if is_complete:
        message = (
            "Полный расчёт выполнен: накопленная оценка — "
            f"{_format_decimal(score)}."
        )
    else:
        message = (
            "Неполный расчёт: учтён только вклад известных оценок — "
            f"{_format_decimal(score)}."
        )

    return {
        "subject_id": subject["id"],
        "subject_name": subject["name"],
        "raw_score": raw_score,
        "score": score,
        "score_cap": score_cap,
        "is_complete": is_complete,
        "missing_components": missing_components,
        "rounding_policy": subject["rounding_policy"],
        "rounded_grade": rounded_grade,
        "contributions": contributions,
        "message": message,
    }
