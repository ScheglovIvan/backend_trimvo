# Trimvo — Project Documentation

## Назначение проекта

Trimvo — бэкенд для мобильного приложения генерации видео на основе шаблонов. Пользователи тратят гемы (внутренняя валюта) для генерации видео из предзаписанных шаблонов, подставляя свои фото. Проект включает: FastAPI REST API, систему асинхронной обработки видео через воркеры (RabbitMQ), хранение файлов в Cloudflare R2 (S3-совместимом), PostgreSQL базу данных и React-административную панель.

---

## Tech Stack

| Компонент | Версия / решение |
|-----------|-----------------|
| Язык | Python 3.11+ |
| Веб-фреймворк | FastAPI 0.111.0 |
| Сервер | Uvicorn 0.29.0 |
| ORM | SQLAlchemy 2.0.30 (синхронный) |
| Миграции | Alembic 1.13.1 |
| База данных | PostgreSQL 15 |
| Очереди | RabbitMQ 3 (pika 1.3.2) |
| Кэш (подключён, но не используется в API) | Redis 7 (redis 5.0.4) |
| Хранилище файлов | Cloudflare R2 (boto3 ≥1.34.0) |
| Видеообработка | FFmpeg (subprocess) + Pillow 10.3.0 |
| Аутентификация | JWT (python-jose 3.3.0) + bcrypt (passlib 1.7.4) |
| Валидация | Pydantic 2.7.1 + pydantic-settings 2.2.1 |
| HTTP-клиент | httpx 0.27.0 |
| Admin UI | React + TypeScript + Vite |
| Контейнеризация | Docker Compose |

---

## Таблица зависимостей (api/requirements.txt)

| Пакет | Версия | Назначение |
|-------|--------|------------|
| fastapi | 0.111.0 | Web-фреймворк |
| uvicorn[standard] | 0.29.0 | ASGI-сервер |
| sqlalchemy | 2.0.30 | ORM |
| alembic | 1.13.1 | Миграции БД |
| asyncpg | 0.29.0 | Async PostgreSQL драйвер (зарезервирован) |
| psycopg2-binary | 2.9.9 | Sync PostgreSQL драйвер (используется) |
| pydantic | 2.7.1 | Валидация данных |
| pydantic-settings | 2.2.1 | Загрузка конфига из .env |
| python-jose[cryptography] | 3.3.0 | JWT токены |
| passlib[bcrypt] | 1.7.4 | Хэширование паролей |
| bcrypt | 3.2.2 | Bcrypt (зафиксирован из-за совместимости) |
| python-multipart | 0.0.9 | Поддержка form-data (загрузка файлов) |
| pika | 1.3.2 | RabbitMQ клиент (зафиксирован из-за совместимости) |
| boto3 | ≥1.34.0 | Cloudflare R2 / S3 клиент |
| redis | 5.0.4 | Redis клиент |
| Pillow | 10.3.0 | Генерация заглушки-превью в preproc_worker |
| httpx | 0.27.0 | HTTP клиент (зарезервирован) |

---

## Структура проекта

```
beckend_trimvo/
├── docker-compose.yml          # Конфигурация всех сервисов
├── .env                        # Переменные окружения (не в git)
├── .env.example                # Пример .env
├── PROJECT.md                  # Этот файл
├── ARCHITECTURE.md             # Архитектурная документация
├── API_RULES.md                # Правила API
├── CLAUDE.md                   # Инструкция для AI-ассистента
│
├── api/                        # FastAPI приложение
│   ├── main.py                 # Точка входа, регистрация роутеров, CORS
│   ├── entrypoint.sh           # Docker: alembic upgrade head → uvicorn
│   ├── requirements.txt        # Python зависимости
│   ├── alembic.ini             # Конфиг миграций
│   │
│   ├── core/                   # Инфраструктурные утилиты
│   │   ├── config.py           # Settings (pydantic-settings, .env)
│   │   ├── database.py         # SQLAlchemy engine + SessionLocal + Base
│   │   ├── security.py         # JWT, bcrypt
│   │   └── dependencies.py     # FastAPI зависимости: get_current_user, get_admin_user
│   │
│   ├── models/                 # SQLAlchemy ORM модели (таблицы БД)
│   │   ├── user.py
│   │   ├── template.py
│   │   ├── job.py
│   │   ├── category.py         # Category + CategoryTemplate (M2M)
│   │   ├── gem_package.py
│   │   ├── gem_transaction.py
│   │   ├── subscription_plan.py
│   │   ├── trend.py
│   │   ├── report.py
│   │   └── admin_config.py     # AdminConfig (key-value) + AuditLog
│   │
│   ├── schemas/                # Pydantic схемы запросов/ответов
│   │   ├── user.py
│   │   ├── template.py
│   │   ├── job.py
│   │   ├── gem_package.py
│   │   ├── subscription_plan.py
│   │   ├── report.py
│   │   └── admin_config.py
│   │
│   ├── routers/                # FastAPI роутеры (публичные + авторизованные)
│   │   ├── auth.py             # /v1/auth/*
│   │   ├── templates.py        # /v1/templates/*
│   │   ├── jobs.py             # /v1/jobs/*
│   │   ├── me.py               # /v1/me/* (gems, daily bonus, transactions)
│   │   ├── payments.py         # /v1/payments/webhook
│   │   ├── gem_packages.py     # /v1/gem-packages
│   │   ├── subscription_plans.py # /v1/subscription-plans
│   │   ├── categories.py       # /v1/categories
│   │   ├── reports.py          # /v1/reports
│   │   ├── config.py           # /v1/config/* (публичные настройки)
│   │   └── admin/              # /v1/admin/* (только role=admin)
│   │       ├── templates.py
│   │       ├── categories.py
│   │       ├── trends.py
│   │       ├── users.py
│   │       ├── jobs.py
│   │       ├── reports.py
│   │       ├── gem_packages.py
│   │       ├── subscription_plans.py
│   │       ├── pricing.py
│   │       ├── config.py       # stub / ai / onboarding-video
│   │       ├── stub.py
│   │       ├── audit.py
│   │       └── stats.py
│   │
│   ├── services/               # Бизнес-логика
│   │   ├── gems.py             # Операции с гемами (deduct/add/refund)
│   │   ├── queue.py            # Публикация сообщений в RabbitMQ
│   │   ├── storage.py          # Cloudflare R2 клиент (boto3: upload/download/signed URLs)
│   │   ├── media_processor.py  # FFmpeg: thumb/preview/gif генерация
│   │   └── stub_ai.py          # Симуляция AI генерации (stub)
│   │
│   ├── workers/                # RabbitMQ воркеры (отдельные процессы)
│   │   ├── preproc_worker.py   # jobs.preproc → jobs.generator
│   │   ├── generator_worker.py # jobs.generator → jobs.postproc (stub AI)
│   │   ├── postproc_worker.py  # jobs.postproc → signed URL → done
│   │   └── thumbnail_worker.py # templates.thumbnail → FFmpeg обработка
│   │
│   └── alembic/
│       └── versions/           # Файлы миграций
│
└── admin/                      # React/TypeScript Admin UI
    ├── src/
    │   ├── App.tsx
    │   ├── api/client.ts       # HTTP клиент для API
    │   └── pages/              # Страницы: Users, Templates, Jobs, etc.
    └── vite.config.ts
```

---

## Как запустить локально

### Вариант 1: Docker Compose (рекомендуется)

```bash
# 1. Скопировать переменные окружения
cp .env.example .env
# При необходимости отредактировать .env (R2 credentials)

# 2. Запустить все сервисы
docker compose up --build

# API доступно на:  http://localhost:8000
# Admin UI:         http://localhost:3000
# RabbitMQ UI:      http://localhost:15672 (guest/guest)
# PostgreSQL:       localhost:5432 (postgres/postgres, db: trimvo)
# Cloudflare R2:    https://dash.cloudflare.com (R2 dashboard)

# 3. (Опционально) Загрузить тестовые данные
docker compose exec api python seed.py
```

### Вариант 2: Запуск без Docker (разработка)

```bash
# Требуется: PostgreSQL, RabbitMQ, Redis запущены локально; R2 credentials в .env

cd api

# 1. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Настроить .env (указать localhost-адреса для сервисов)
cp ../.env.example .env

# 4. Применить миграции
alembic upgrade head

# 5. Запустить API
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 6. Запустить воркеры (в отдельных терминалах)
python workers/preproc_worker.py
python workers/generator_worker.py
python workers/postproc_worker.py
python workers/thumbnail_worker.py
```

---

## Переменные окружения

| Переменная | Тип | Назначение | Пример |
|-----------|-----|------------|--------|
| `DATABASE_URL` | string | PostgreSQL DSN | `postgresql://postgres:postgres@postgres:5432/trimvo` |
| `REDIS_URL` | string | Redis DSN | `redis://redis:6379` |
| `RABBITMQ_URL` | string | RabbitMQ AMQP URL | `amqp://guest:guest@rabbitmq:5672/` |
| `R2_ENDPOINT` | string | R2 S3-совместимый endpoint | `https://<account_id>.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY_ID` | string | R2 Access Key ID | — |
| `R2_SECRET_ACCESS_KEY` | string | R2 Secret Access Key | — |
| `R2_PUBLIC_URL_TEMPLATES` | string | Публичный URL бакета templates | `https://pub-xxxx.r2.dev` |
| `R2_BUCKET_UPLOADS` | string | Bucket для загружаемых файлов | `uploads` |
| `R2_BUCKET_RESULTS` | string | Bucket для готовых видео | `results` |
| `R2_BUCKET_TEMPLATES` | string | Bucket для шаблонов | `templates` |
| `JWT_SECRET` | string | Секрет для подписи JWT | `your-secret-key-change-in-production` |
| `JWT_ALGORITHM` | string | Алгоритм JWT | `HS256` |
| `JWT_EXPIRE_MINUTES` | int | Время жизни access token | `43200` (30 дней) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | int | Время жизни refresh token | `30` |
| `STUB_MODE` | bool | Использовать заглушку вместо AI | `true` |
| `STUB_LATENCY_MS` | int | Задержка stub генерации (мс) | `10000` |
| `STUB_SUCCESS_RATE` | float | Доля успешных stub генераций | `0.8` |
| `ADMIN_EMAIL` | string | Email первого admin пользователя | `admin@trimvo.com` |
| `ADMIN_PASSWORD` | string | Пароль первого admin | `admin123` |

> **ВАЖНО**: `R2_PUBLIC_URL_TEMPLATES` — публичный URL бакета `templates` из Cloudflare R2 dashboard (Settings → Public Access). Бакеты `uploads` и `results` остаются приватными, доступ через presigned URLs (7 дней).

---

## Известные проблемы и TODO

### В коде

- **`asyncpg` установлен, но не используется** — `database.py` использует синхронный `psycopg2`. При миграции на async нужно переписать все роутеры.
- **Redis подключён как зависимость, но нигде не используется** — зарезервирован для будущего кэширования.
- **`stub_ai.py` не используется напрямую** — логика заглушки дублирована прямо в `generator_worker.py`.
- **Non-stub AI не реализован** — `generator_worker.py:95`: `"Non-stub mode not implemented"` — при `STUB_MODE=false` все джобы падают.
- **Отсутствует валидация `reason` в `POST /v1/reports`** — список `VALID_REASONS` определён в `schemas/report.py`, но не применяется к `ReportCreate`.
- **Платёжный webhook без верификации подписи** — `payments.py` принимает `x_signature` заголовок, но не проверяет его.
- **`JWT_EXPIRE_MINUTES` в `.env.example` = 60, но в `config.py` default = 43200** — расхождение.
- **Hardcoded значения**: `gems_cost` по умолчанию `200` встречается в нескольких местах (template, jobs router, admin templates router).
- **`TASK_backend_diagnostic.md`** в корне — рабочий файл диагностики, не является частью кода.

### Тестирование

- Тестов нет совсем (`pytest` не в зависимостях).
