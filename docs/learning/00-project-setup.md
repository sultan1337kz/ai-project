# 00 — Настройка проекта: uv, pyproject.toml, src-layout, mypy

## 1. Что делает этот шаг

Бизнес-логики пока нет. Этот шаг собирает каркас, на котором будут работать все остальные модули:
- воспроизводимое окружение (одинаковые версии Python и зависимостей у меня, в CI и позже в Docker);
- пакет `triage`, который устанавливается в venv;
- quality gates: `ruff`, `mypy` и `pytest`, которые CI запускает на каждом push и PR.

Место в пайплайне: это фундамент под всеми этапами
`ingest → normalize → … → create issue`.

## 2. Ключевые концепции

### uv vs pip vs Poetry (и при чём тут Maven/Gradle)

В Java одна связка инструментов (Maven или Gradle) отвечает сразу за всё: зависимости, сборку, тесты и публикацию. В Python эти задачи исторически решали разные утилиты:

| Задача | Java | Классический Python | uv |
|---|---|---|---|
| Версия рантайма | SDKMAN / toolchains в Gradle | pyenv | `uv python install`, `.python-version` |
| Изоляция зависимостей | у каждого проекта свой classpath | `python -m venv` вручную | `.venv` создаётся автоматически |
| Описание зависимостей | `pom.xml` / `build.gradle` | `requirements.txt` | `pyproject.toml` |
| Фиксация версий | Gradle lockfile / dependencyManagement | `pip freeze` (вручную) | `uv.lock` (автоматически, кросс-платформенный) |
| Запуск задач | `mvn test`, `gradle check` | `pip install …; pytest` | `uv run pytest` |
| Сборка пакета | `mvn package` → jar | `python -m build` | `uv build` → wheel |

- **pip** только устанавливает пакеты. Lock-файла у него нет: `requirements.txt` с `==` — это ручная имитация. Транзитивные зависимости он не разрешает «честно», и каждый следующий `pip install` может сломать уже установленное.
- **Poetry** ближе всего к Gradle: `pyproject.toml`, lock-файл, venv и сборка в одном инструменте. Минусы: он медленный (резолвер на Python), исторически использовал собственный формат секций `[tool.poetry]`, а версией Python не управляет.
- **uv** (Astral, на Rust) закрывает те же задачи, что Poetry, плюс управляет версией Python. Он в 10–100 раз быстрее и следует стандартам: `[project]` по PEP 621, `[dependency-groups]` по PEP 735. Аналогия: «Gradle с Gradle Wrapper и встроенным SDKMAN».

Что важно знать про uv:
- `uv add X` записывает зависимость в `pyproject.toml`, обновляет `uv.lock` и сразу ставит пакет в `.venv`.
- `uv run <cmd>` перед запуском синхронизирует окружение с lock-файлом, поэтому про `source .venv/bin/activate` можно не думать.
- `uv sync --locked` в CI падает, если `uv.lock` не соответствует `pyproject.toml`. Ближайшая аналогия — `npm ci` или Gradle `--write-locks` наоборот: CI проверяет, что lock не забыли закоммитить.

### pyproject.toml — «pom.xml для Python»

Один файл вместо зоопарка из `setup.py`, `setup.cfg`, `requirements.txt`, `mypy.ini` и `.flake8`.

```toml
[project]              # метаданные пакета (≈ groupId/artifactId/version + <dependencies>)
dependencies = []      # runtime-зависимости (≈ scope compile)

[dependency-groups]    # dev-зависимости, в wheel не попадают (≈ scope test/provided)
dev = ["mypy", "pytest", "ruff"]

[build-system]         # чем собирать пакет (≈ maven-jar-plugin)
build-backend = "uv_build"

[tool.ruff] / [tool.mypy] / [tool.pytest.ini_options]
                       # настройки инструментов (≈ <plugins><configuration>)
```

Версии в `pyproject.toml` указываются диапазонами (`>=9.1.1`), а точные версии хранит `uv.lock`. Это как version range в `pom.xml` вместе с lockfile.

### Структура Python-пакета и src-layout

```
src/triage/__init__.py         # наличие __init__.py делает каталог пакетом (≈ Java package)
src/triage/models.py           # модуль = один .py-файл (≈ класс/файл, но может содержать много всего)
src/triage/parsers/__init__.py # подпакет
src/triage/py.typed            # маркер PEP 561: «пакет поставляет type hints»
```

- **Пакет**: каталог с `__init__.py`. Код в `__init__.py` выполняется при первом `import triage`, поэтому мы держим его пустым (только docstring) и не создаём побочных эффектов при импорте.
- **Почему `src/`?** При flat-layout (`triage/` в корне) Python находит пакет прямо в текущей папке, потому что она лежит в `sys.path`. Тогда тесты проходят даже с поломанной упаковкой: например, если забыли включить файл в wheel или в Docker-образ. С `src/` пакет доступен **только** после установки в venv, и такие ошибки проявляются сразу. Smoke-тест `tests/test_smoke.py` проверяет как раз это.
- В Java такой проблемы нет, потому что classpath собирает build tool. В Python `sys.path` формируется во время выполнения, отсюда и ловушка.
- `lab/`, `reports/` и `evals/` не являются Python-пакетами, поэтому в них только `.gitkeep`: git не хранит пустые каталоги.

### Зачем mypy в динамическом языке

Type hints (`def f(x: int) -> str`) интерпретатор **не проверяет** во время выполнения: для него это просто аннотации. mypy — отдельный статический анализатор. По сути это «javac без компиляции».

Зачем это нужно в нашем проекте:
- Узлы LangGraph передают друг другу общий state, а MCP-tools принимают и возвращают структуры. Опечатка в ключе или `None` там, где ждали `Finding`, без mypy проявится только в рантайме, возможно, на середине дорогого LLM-прогона.
- `strict = true` запрещает функции без аннотаций, неявный `Any` и `Optional` без проверки на `None`. Это ближе всего к Java-опыту.
- Цена: некоторые библиотеки плохо типизированы. Для них ослабляем проверки точечно через `[[tool.mypy.overrides]]` с `module = "litellm.*"`, а не выключаем strict глобально.

Чем mypy не является: это не валидация входных данных. JSON из отчёта ZAP mypy проверить не может. Для этого будет pydantic: он проверяет данные во время выполнения, примерно как Bean Validation.

### ruff

Один инструмент на Rust заменяет flake8, isort, pyupgrade, black и десяток плагинов. Аналог в Java — Checkstyle + SpotBugs (частично) + Spotless. В CI запускаем `ruff check` (линт) и `ruff format --check` (форматирование).

## 3. Python-особенности этого шага

- `.python-version` — файл, по которому uv (и pyenv) выбирают интерпретатор.
- `-> None` у тестов: в strict mypy аннотацию возврата нужно указывать даже у функций, которые ничего не возвращают.
- `pytest` находит тесты по соглашению об именах (`test_*.py`, `def test_*`) без аннотаций вроде `@Test`. `--import-mode=importlib` — рекомендованный режим: pytest не дописывает папку `tests/` в `sys.path`.
- pytest возвращает exit code 5, если не нашёл ни одного теста, и CI считает это ошибкой. Ещё одна причина держать smoke-тест.

## 4. Альтернативы

- **Poetry**: зрелый, но медленнее и не управляет версией Python. Отказались.
- **pip + requirements.txt + venv**: нет нормального lock-файла и несколько инструментов вместо одного. Отказались.
- **Flat-layout**: проще на один уровень вложенности, но маскирует ошибки упаковки. Отказались.
- **hatchling / setuptools как build backend**: работают, но `uv_build` проще и быстрее для чистого Python-пакета. При необходимости переход меняет одну строку в `[build-system]`.
- **pyright вместо mypy**: быстрее и строже в некоторых местах. mypy выбрали как самый распространённый стандарт, который ожидают увидеть ревьюеры.
- Подробности — в `DECISIONS.md`, ADR-001.

## 5. Что может сломаться

| Симптом | Причина |
|---|---|
| CI: `The lockfile at uv.lock needs to be updated` | поменяли `pyproject.toml`, но не закоммитили `uv.lock` → `uv lock` и коммит |
| `ModuleNotFoundError: No module named 'triage'` | запуск без `uv run` (не тот Python) или пакет не установлен → `uv sync` |
| pytest: `no tests ran`, exit code 5 | тестов нет или файлы названы не по шаблону `test_*.py` |
| mypy: `Skipping analyzing "X": module is installed, but missing library stubs` | у библиотеки нет type hints → поставить `types-X` или добавить override |
| CI падает на `ruff format --check` | забыли `uv run ruff format .` локально |

## 6. Вопросы для самопроверки

1. Чем `uv.lock` отличается от диапазонов версий в `pyproject.toml` и зачем нужны оба?
2. Какую конкретную ошибку предотвращает src-layout по сравнению с flat-layout?
3. Проверяет ли Python type hints во время выполнения? Какую роль тогда играют mypy и pydantic?
4. Почему dev-зависимости вынесены в `[dependency-groups]`, а не в `[project].dependencies`?
5. Что делает флаг `--locked` в CI и что произойдёт без него?

## 7. Упражнение

Добавь в `src/triage/__init__.py` функцию `def version() -> str`, которая возвращает версию пакета через `importlib.metadata.version("triage")`, и тест на неё. Потом намеренно убери `-> str` и запусти `uv run mypy src`: посмотри, что скажет strict-режим. Верни аннотацию и прогони `ruff`, `mypy` и `pytest`.
