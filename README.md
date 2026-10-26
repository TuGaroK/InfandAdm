# Калькулятор накопленной оценки

Сервис для студента: по одному из трёх учебных предметов показывает формулу накопленной оценки, принимает оценки в запросе и возвращает вклад каждого компонента. Оценки используются только в этом расчёте.

Основной интерфейс — интерактивная документация FastAPI: <http://127.0.0.1:8000/docs>.

За основу взят `app_final.py` из архива занятия 4, который предоставил преподаватель. Публичной ссылки на этот архив нет. Для этого проекта добавлены:

- каталог трёх предметов и выдача формулы из тех же коэффициентов, по которым идёт расчёт;
- расчёт полного и частичного накопа на `Decimal`, с ограничением суммы значением 10;
- проверка оценок и отдельные сообщения для значений вне диапазона 0..10;
- настройки `APP_NAME`, `APP_VERSION` и `LOG_LEVEL`;
- журналирование запуска и результата расчёта;
- автоматические тесты и проверка в GitHub Actions.

## Предметы и формулы

Идентификаторы предметов: `discrete`, `python`, `infrastructure`. Каждая введённая оценка — конечное JSON-число от 0 до 10 включительно. Промежуточные произведения и сумма не округляются. `raw_score` — сумма известных вкладов до ограничения, `score = min(raw_score, 10)`.

### Дискретные и непрерывные структуры (`discrete`)

`S = 0.2*hw1 + 0.2*hw2 + 0.1*test1 + 0.1*test2 + 0.4*exam + 0.1*participation; score = min(S, 10).`

| Компонент | Подпись | Вес |
| --- | --- | ---: |
| `hw1` | ДЗ №1 | 0.2 |
| `hw2` | ДЗ №2 | 0.2 |
| `test1` | Контрольная №1 | 0.1 |
| `test2` | Контрольная №2 | 0.1 |
| `exam` | Экзамен | 0.4 |
| `participation` | Работа на занятиях | 0.1 |

Коэффициенты суммируются в 1.1. Это ожидаемо: веса не делятся на 1.1 и не приводятся к 1. Если все шесть оценок равны 10, сумма вкладов равна 11, а `score` становится 10. Ограничение применяется только к сумме. Введённое число больше 10, например 10.5, остаётся ошибкой и не заменяется на 10.

Правило округления дискретки неизвестно: `rounding_policy` равен `unknown`, а `rounded_grade` равен `null` и при полном, и при неполном вводе. Рабочий результат — дробный `score`.

### Программирование на Python (`python`)

`S = 0.1*homework_avg + 0.2*mini_tests_avg + 0.2*independent_avg + 0.5*exam; score = min(S, 10).`

Пользователь передаёт три уже посчитанных средних и экзамен, а не отдельные домашние задания, мини-тесты и самостоятельные работы:

| Компонент | Подпись | Вес |
| --- | --- | ---: |
| `homework_avg` | Средняя оценка за домашние задания | 0.1 |
| `mini_tests_avg` | Средняя оценка за мини-тесты | 0.2 |
| `independent_avg` | Средняя оценка за самостоятельные работы | 0.2 |
| `exam` | Экзамен | 0.5 |

При полном вводе итог дополнительно округляется до целого арифметически, значение с дробной частью 0.5 — вверх. Дробный `score` при этом сохраняется. Например, четыре оценки 4.5 дают `score` 4.5 и `rounded_grade` 5; четыре оценки 6.5 дают `score` 6.5 и `rounded_grade` 7.

### Инфраструктура и администрирование (`infrastructure`)

`S = project; score = min(S, 10).`

В формуле один компонент: итоговый проект с весом 1. Отдельный экзамен не добавляется. При полном вводе округление такое же, как у Python: `score` остаётся дробным, а `rounded_grade` показывает целое с правилом «0.5 вверх». Проект 8.5 даёт `score` 8.5 и `rounded_grade` 9; проект 9.5 даёт `score` 9.5 и `rounded_grade` 10.

## Подготовка

Нужен Python 3.12. Эта копия проверена на Python 3.12.4. Команды выполняются из корня репозитория. Для запуска сервиса достаточно `requirements.txt`. Для тестов установите `requirements-dev.txt`: он подключает зависимости запуска и добавляет pytest и httpx.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Только запуск, без тестов:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Bash

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Только запуск, без тестов:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## Настройки

`.env.example` перечисляет те же переменные, которые читает сервис, и их значения по умолчанию. Приложение не загружает `.env` и `.env.example` само: значение берётся из окружения процесса. Переменные задают в том же сеансе терминала, в котором затем запускают Uvicorn.

| Переменная | По умолчанию | Где виден результат |
| --- | --- | --- |
| `APP_NAME` | `Калькулятор накопа` | текст `GET /`, заголовок `/docs`, строка запуска в журнале |
| `APP_VERSION` | `0.1.0` | `GET /version`, поле версии в `/docs`, строка запуска в журнале |
| `LOG_LEVEL` | `INFO` | уровень сообщений приложения в терминале |

Допустимы стандартные имена уровней Python: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Регистр и пробелы по краям не важны. Неизвестное значение, например `verbose`, заменяется на `INFO`; в терминале появляется предупреждение `Неизвестный LOG_LEVEL=...; используется INFO.`

Запуск и успешный расчёт пишутся на уровне `INFO`, ошибки расчёта и проверки запроса — на уровне `WARNING`. Уровень выше `INFO` скрывает сообщение о запуске и об успешном расчёте.

### Windows PowerShell

```powershell
$env:APP_NAME = "Калькулятор группы"
$env:APP_VERSION = "0.1.0"
$env:LOG_LEVEL = "INFO"
.\.venv\Scripts\python.exe -m uvicorn app_final:app
```

Проверка названия и версии:

```powershell
curl.exe -s http://127.0.0.1:8000/
curl.exe -s http://127.0.0.1:8000/version
```

При `APP_NAME=Калькулятор группы` ответ корня содержит `Сервис «Калькулятор группы» работает`. `GET /version` возвращает `{"version":"0.1.0"}`.

### Bash

```bash
export APP_NAME="Калькулятор группы"
export APP_VERSION="0.1.0"
export LOG_LEVEL="INFO"
.venv/bin/python -m uvicorn app_final:app
```

```bash
curl -s http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/version
```

## Запуск

Обычная работа, без автоматической перезагрузки.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app_final:app
```

Bash:

```bash
.venv/bin/python -m uvicorn app_final:app
```

Разработка, с перезагрузкой при изменении файлов.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app_final:app --reload
```

Bash:

```bash
.venv/bin/python -m uvicorn app_final:app --reload
```

После строки `Application startup complete` открываются:

- приложение: <http://127.0.0.1:8000/> — `{"message":"Сервис «Калькулятор накопа» работает","docs":"/docs"}`;
- состояние: <http://127.0.0.1:8000/health> — `{"status":"ok"}`;
- версия: <http://127.0.0.1:8000/version> — `{"version":"0.1.0"}`;
- документация: <http://127.0.0.1:8000/docs>.

Остановка — Ctrl+C в том же терминале. В журнале появляется сообщение об остановке сервиса.

## Маршруты предметов

- `GET /subjects` — список из трёх предметов, поля `id` и `name`;
- `GET /subjects/{subject_id}` — формула, компоненты, коэффициенты, диапазон 0..10, ограничение суммы и пояснение округления;
- `POST /subjects/{subject_id}/calculate` — расчёт по телу `{"grades": {...}}`.

Неизвестный `subject_id` на обоих маршрутах даёт HTTP 404 и текст `Предмет с идентификатором '...' не найден.`

В PowerShell для запросов ниже используйте `curl.exe`, а не `curl`: имя `curl` вызывает другой командлет. У команд POST перед параметрами стоит `--%`. Без этого символа PowerShell убирает двойные кавычки из JSON, и сервис отвечает `422` с типом `json_invalid`. GET-запросы не содержат кавычек в теле, для них `--%` не нужен.

### Полный расчёт: дискретка

`POST /subjects/discrete/calculate`

```json
{
  "grades": {
    "hw1": 6.5,
    "hw2": 8.5,
    "test1": 7,
    "test2": 8,
    "exam": 9,
    "participation": 10
  }
}
```

Ответ `200`:

```json
{
  "subject_id": "discrete",
  "subject_name": "Дискретные и непрерывные структуры",
  "raw_score": 9.1,
  "score": 9.1,
  "score_cap": 10,
  "is_complete": true,
  "missing_components": [],
  "rounding_policy": "unknown",
  "rounded_grade": null,
  "contributions": [
    {"id": "hw1", "label": "ДЗ №1", "weight": 0.2, "grade": 6.5, "contribution": 1.3},
    {"id": "hw2", "label": "ДЗ №2", "weight": 0.2, "grade": 8.5, "contribution": 1.7},
    {"id": "test1", "label": "Контрольная №1", "weight": 0.1, "grade": 7, "contribution": 0.7},
    {"id": "test2", "label": "Контрольная №2", "weight": 0.1, "grade": 8, "contribution": 0.8},
    {"id": "exam", "label": "Экзамен", "weight": 0.4, "grade": 9, "contribution": 3.6},
    {"id": "participation", "label": "Работа на занятиях", "weight": 0.1, "grade": 10, "contribution": 1}
  ],
  "message": "Полный расчёт выполнен: накопленная оценка — 9.1."
}
```

Windows PowerShell:

```powershell
curl.exe --% -s -X POST http://127.0.0.1:8000/subjects/discrete/calculate -H "Content-Type: application/json" -d "{\"grades\":{\"hw1\":6.5,\"hw2\":8.5,\"test1\":7,\"test2\":8,\"exam\":9,\"participation\":10}}"
```

Bash:

```bash
curl -s -X POST http://127.0.0.1:8000/subjects/discrete/calculate \
  -H "Content-Type: application/json" \
  -d '{"grades":{"hw1":6.5,"hw2":8.5,"test1":7,"test2":8,"exam":9,"participation":10}}'
```

### Полный расчёт: Python

`POST /subjects/python/calculate`

```json
{
  "grades": {
    "homework_avg": 6.5,
    "mini_tests_avg": 8.5,
    "independent_avg": 7,
    "exam": 8
  }
}
```

Ответ `200`: `raw_score` и `score` равны 7.75, `rounded_grade` равен 8, `is_complete` равен `true`. Вклады: домашние 0.65, мини-тесты 1.7, самостоятельные 1.4, экзамен 4. Сообщение: `Полный расчёт выполнен: накопленная оценка — 7.75.`

Windows PowerShell:

```powershell
curl.exe --% -s -X POST http://127.0.0.1:8000/subjects/python/calculate -H "Content-Type: application/json" -d "{\"grades\":{\"homework_avg\":6.5,\"mini_tests_avg\":8.5,\"independent_avg\":7,\"exam\":8}}"
```

Bash:

```bash
curl -s -X POST http://127.0.0.1:8000/subjects/python/calculate \
  -H "Content-Type: application/json" \
  -d '{"grades":{"homework_avg":6.5,"mini_tests_avg":8.5,"independent_avg":7,"exam":8}}'
```

### Полный расчёт: инфраструктура

`POST /subjects/infrastructure/calculate`

```json
{
  "grades": {
    "project": 8.5
  }
}
```

Ответ `200`: `raw_score` и `score` равны 8.5, `rounded_grade` равен 9, вклад проекта равен 8.5. Сообщение: `Полный расчёт выполнен: накопленная оценка — 8.5.`

Windows PowerShell:

```powershell
curl.exe --% -s -X POST http://127.0.0.1:8000/subjects/infrastructure/calculate -H "Content-Type: application/json" -d "{\"grades\":{\"project\":8.5}}"
```

Bash:

```bash
curl -s -X POST http://127.0.0.1:8000/subjects/infrastructure/calculate \
  -H "Content-Type: application/json" \
  -d '{"grades":{"project":8.5}}'
```

## Частичный накоп

Отсутствующий ключ и значение `null` означают, что оценка пока неизвестна. Число `0` означает уже полученный ноль: компонент известен, его вклад равен 0.

В неполном расчёте складываются только известные вклады, без нормировки на недостающие веса. `is_complete` равен `false`, `missing_components` перечисляет неизвестные компоненты в порядке предмета, у неизвестного компонента `grade` и `contribution` равны `null`. `score` здесь — уже набранный вклад, а не обещание итоговой оценки. `rounded_grade` при неполном вводе всегда `null`, в том числе у Python и инфраструктуры.

Пример: у дискретки переданы только `hw1` 6.5 и `hw2` 8.5. Ответ содержит `raw_score` 3, `score` 3, пропуски `test1`, `test2`, `exam`, `participation` и сообщение `Неполный расчёт: учтён только вклад известных оценок — 3.`

Если известной оценки нет совсем — пустой объект, все поля отсутствуют или все равны `null`, — сервис отвечает `422`: `Нечего рассчитывать: укажите хотя бы одну известную оценку.` Один компонент со значением 0 при остальных пропусках остаётся допустимым неполным расчётом со `score` 0.

## score и rounded_grade

`score` всегда сохраняет дробную часть и не заменяется округлением. `rounded_grade` — отдельное поле:

- дискретка: всегда `null`, потому что правило округления неизвестно;
- Python и инфраструктура: целое только при полном вводе, арифметически, 0.5 вверх; при неполном вводе `null`.

Так проект 8.5 одновременно показывает накоп 8.5 и округлённую оценку 9. Округление не меняет вклады компонентов.

## Ошибки

Оценка выше 10 не обрезается до допустимой границы. `POST /subjects/infrastructure/calculate` с телом ниже возвращает `422`:

```json
{
  "grades": {
    "project": 10.5
  }
}
```

```json
{
  "detail": [
    {
      "loc": ["body", "grades", "project"],
      "type": "grade_too_high",
      "msg": "Вы непризнанный гений или просто ошиблись числом?",
      "hint": "Оценка должна быть числом от 0 до 10 включительно."
    }
  ]
}
```

Windows PowerShell:

```powershell
curl.exe --% -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8000/subjects/infrastructure/calculate -H "Content-Type: application/json" -d "{\"grades\":{\"project\":10.5}}"
```

Bash:

```bash
curl -s -X POST http://127.0.0.1:8000/subjects/infrastructure/calculate \
  -H "Content-Type: application/json" \
  -d '{"grades":{"project":10.5}}'
```

Оценка ниже 0 тоже даёт `422`, тип `grade_too_low` и текст `Ничего страшного, Цезарь тоже не сразу стал салатом.` В `loc` указано конкретное поле, например `["body", "grades", "exam"]`.

Также отклоняются строка `"6.5"`, `true` и `false`, массивы, объекты, `NaN`, бесконечность, неизвестный ключ компонента и лишние поля рядом с `grades`. У `grades` должен быть JSON-объект. Такие ответы имеют статус `422` и не превращаются в ошибку сервера `500`.

## Логи

Журнал пишется в терминал, где запущено приложение, в поток ошибок процесса. Отдельный файл журнала не создаётся. Формат строки приложения: время, уровень, имя `grade_calculator`, сообщение.

При обычном запуске видна строка:

```text
Запуск сервиса «Калькулятор накопа» версии 0.1.0 (LOG_LEVEL=INFO).
```

Успешный расчёт выглядит так: `Расчёт выполнен: subject=python complete=True missing=0.` Ошибка выглядит так: `Ошибка расчёта: subject=infrastructure status=422 type=grade_too_high.` В этих строках нет введённых оценок и полного тела запроса. Рядом Uvicorn пишет собственные строки о старте процесса и HTTP-запросах.

## Диагностика

### Неверный интерпретатор

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe --version
```

Bash:

```bash
.venv/bin/python --version
```

Ожидается Python 3.12.x. Если команда `python` показывает другую версию или не находит модули, вызывайте интерпретатор из `.venv`, как в командах выше.

### Недостающие зависимости

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -c "import fastapi, uvicorn"
```

Bash:

```bash
.venv/bin/python -c "import fastapi, uvicorn"
```

`ModuleNotFoundError` означает, что зависимости не установлены в это окружение. Повторите `pip install` тем же интерпретатором. Пакеты, поставленные в другой Python, этот venv не видит.

### Неверная точка входа

Рабочая команда указывает приложение `app_final:app`. Команда с `app:app` завершается до приёма запросов: Uvicorn сообщает `Could not import module "app"`. Файла `app.py` в проекте нет.

### Занятый порт

Если предыдущий процесс ещё слушает порт 8000, новый запуск печатает `Application startup complete`, затем останавливается. Отличительная строка: `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`. Остановите прежний процесс через Ctrl+C либо выберите другой порт.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app_final:app --port 8001
```

Bash:

```bash
.venv/bin/python -m uvicorn app_final:app --port 8001
```

Тогда адрес сервиса — <http://127.0.0.1:8001/>. Каталог предметов читается рядом с `app_final.py`, поэтому текущая папка терминала на поиск `data/subjects.json` не влияет.

## Тесты

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Bash:

```bash
.venv/bin/python -m pytest -v
```

## GitHub Actions

При `push` и `pull_request` workflow `.github/workflows/ci.yml` ставит зависимости из `requirements-dev.txt` на Python 3.12, запускает `python -m pytest -v` и после успешного прогона собирает архив `grade-calculator.zip`. В архив входят код, `data/subjects.json`, зависимости, тесты, этот README и `.env.example`.
