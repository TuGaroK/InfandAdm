"""Расчёт накопленной оценки без зависимости от HTTP."""

from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _as_decimal(value: int | float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def calculate_subject(
    subject: Mapping[str, Any],
    grades: Mapping[str, int | float | Decimal],
) -> dict[str, Any]:
    """Рассчитать полный накоп по компонентам предмета."""

    raw_score = Decimal("0")
    contributions = []

    for component in subject["components"]:
        component_id = component["id"]
        weight = Decimal(component["weight"])
        grade = _as_decimal(grades[component_id])
        contribution = grade * weight
        raw_score += contribution
        contributions.append(
            {
                "id": component_id,
                "label": component["label"],
                "weight": weight,
                "grade": grade,
                "contribution": contribution,
            }
        )

    score_cap = _as_decimal(subject["score_cap"])
    score = min(raw_score, score_cap)
    rounded_grade = None
    if subject["rounding_policy"] == "half_up":
        rounded_grade = int(
            score.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

    return {
        "subject_id": subject["id"],
        "subject_name": subject["name"],
        "raw_score": raw_score,
        "score": score,
        "score_cap": score_cap,
        "is_complete": True,
        "missing_components": [],
        "rounding_policy": subject["rounding_policy"],
        "rounded_grade": rounded_grade,
        "contributions": contributions,
        "message": f"Полный расчёт выполнен: накопленная оценка — {score}.",
    }
