# Admission Analysis (Case 3)

Полный проект для кейса «Командный кейс №3 “Анализ поступления”».

## Установка

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Генерация данных (16 CSV)

```bash
python scripts/generate_data.py
```

Файлы создаются в `data/day_01/*.csv` ... `data/day_04/*.csv`.

## Запуск сервера

```bash
uvicorn app.main:app --reload
```

Открыть в браузере: `http://127.0.0.1:8000/`

## Импорт дня

```bash
# пример
curl -X POST http://127.0.0.1:8000/api/import/2025-08-01
```

## Очистка БД

```bash
curl -X POST http://127.0.0.1:8000/api/reset
```

## PDF отчет

```bash
# пример
curl -o report.pdf http://127.0.0.1:8000/api/report/2025-08-01.pdf
```

## Самопроверка

```bash
python scripts/selfcheck.py
```

Selfcheck:
- генерирует данные,
- проверяет размеры и пересечения,
- проверяет обновления между днями,
- импортирует дни в БД,
- проверяет проходные и consent,
- генерирует PDF и проверяет ключевые секции.

## Структура

- `app/` — FastAPI приложение, БД, расчеты, PDF
- `scripts/` — генерация данных и selfcheck
- `data/` — CSV файлы (генерируются)
- `reports/` — PDF отчеты (создаются)