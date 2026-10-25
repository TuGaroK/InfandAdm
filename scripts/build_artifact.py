"""Собрать ZIP приложения по явному списку файлов."""

import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_NAME = "grade-calculator.zip"
FILES = (
    "app_final.py",
    "calculator.py",
    "data/subjects.json",
    "requirements.txt",
    "requirements-dev.txt",
    "test_app.py",
    "README.md",
    ".env.example",
)


def main() -> None:
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit(
            "Нет файлов для архива: " + ", ".join(missing)
        )

    destination = ROOT / ARCHIVE_NAME
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name in FILES:
            archive.write(ROOT / name, arcname=name)

    print(destination)


if __name__ == "__main__":
    main()
