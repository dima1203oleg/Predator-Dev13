Оновлення: «chore: lint fixes and CI» (гілка `chore/ci-lint-fixes-20251113`)

Коротко — що зроблено
- Запущено `ruff` з автофіксом та відформатовано код.
- Замінив небезпечні `except:` на `except Exception:` у кількох модулях (безпечні, локальні зміни).
- Виправив явні синтаксичні/відступні помилки, що блокували тести.
- Додав/оновив мінімальний CI workflow: `.github/workflows/ci-clean.yml` — він встановлює dev-залежності (включно з `pytest-cov`), запускає `ruff` і `pytest` з генерацією `junit.xml` та звіту покриття.

Файли/каталоги, які варто переглянути першочергово
- agents/ — багато безпечних змін, зверніть увагу на: `recommendation_agent.py`, `miner.py`, `speech_recognition_agent.py`, `natural_language_processing_agent.py`, `lora_trainer_agent.py`, `data_quality_agent.py`, `risk_assessment_agent.py`.
- .github/workflows/ci-clean.yml — мінімальний CI для швидкої перевірки.

Як локально відтворити (швидка перевірка)
1) Відкрити середовище Python (рекомендовано 3.11).
2) Встановити dev-залежності (якщо потрібно):

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

3) Запустити лінт та автозаправлення:

```bash
ruff check --fix . && ruff format .
```

4) Запустити тести:

```bash
pytest -q --maxfail=1 --junitxml=reports/junit.xml --cov=. --cov-report=term-missing
```

Що перевірити в CI (як reviewer)
- Чи проходять job-и Actions без помилок (особливо `lint_test`).
- Чи згенеровано `reports/junit.xml` та звіт coverage.
- Чи немає regressions у поведінці агентів (за наявності тестів для них).

Наступні кроки (пропозиції)
- Переглянути та поступово виправити дрібні ruff-повідомлення типу UP006/UP035 (типізація, сучасні builtins) в окремих невеликих PR.
- Додати коротку документацію `docs/dev_setup.md` з командами для локального запуску та діагностики CI.

Якщо хочете, я:
- додам короткий CHANGELOG entry та оновлю PR description (зроблено зараз),
- почну моніторити результати GitHub Actions і вносити фікси за потреби.

