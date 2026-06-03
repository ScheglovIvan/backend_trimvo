# Trimvo — Architecture Documentation

## Диаграмма слоёв

```
Mobile App (Flutter) / Admin UI (React)
           │
           ▼ HTTP/REST
┌─────────────────────────────────────────────────┐
│                  FastAPI (main.py)               │
│  CORS Middleware                                 │
│  HTTPBearer (JWT) — core/dependencies.py        │
├─────────────────────────────────────────────────┤
│             Routers (routers/)                  │
│   /v1/auth  /v1/templates  /v1/jobs  /v1/me    │
│   /v1/payments  /v1/reports  /v1/config        │
│   /v1/admin/**                                  │
├─────────────────────────────────────────────────┤
│             Services (services/)                │
│   gems.py   queue.py   storage.py               │
│   media_processor.py   stub_ai.py               │
├─────────────────────────────────────────────────┤
│   SQLAlchemy ORM (models/) + psycopg2           │
├─────────────────────────────────────────────────┤
│              PostgreSQL 15                      │
└─────────────────────────────────────────────────┘
           │                    │
           ▼                    ▼
     RabbitMQ            Cloudflare R2
     (pika)           (upload/results/templates)
           │
    ┌──────┴──────────────────────────────┐
    │         Workers (отдельные процессы) │
    │  preproc → generator → postproc     │
    │  thumbnail (шаблоны)                │
    └─────────────────────────────────────┘
```

---

## Описание слоёв

### Routers (`api/routers/`)
Принимают HTTP-запросы. Вызывают зависимости (auth), передают данные в сервисы или напрямую работают с ORM. **Не содержат бизнес-логику** (кроме простых CRUD).

### Services (`api/services/`)
- **`gems.py`** — операции с балансом гемов: `deduct_gems`, `add_gems`, `refund_gems`, скидка SVIP, cost calculation.
- **`queue.py`** — публикация в RabbitMQ через pika. Инициирует pipeline воркеров.
- **`storage.py`** — Cloudflare R2 (boto3): upload/download, presigned URLs, bucket check. Единый клиент через S3-совместимый endpoint.
- **`media_processor.py`** — FFmpeg: thumb/preview/gif генерация для шаблонов.
- **`stub_ai.py`** — симуляция AI генерации (задержка + случайный результат). Фактически заменён кодом прямо в `generator_worker.py`.

### Models (`api/models/`)
SQLAlchemy ORM, синхронный режим. Наследуются от `Base` (core/database.py).

### Workers (`api/workers/`)
Отдельные процессы (не треды), слушают RabbitMQ. Используют `SessionLocal()` напрямую.

Pipeline обработки джоба:
```
jobs.preproc → jobs.generator → jobs.postproc
     ↓               ↓                ↓
preproc_worker   generator_worker  postproc_worker
status=queued    status=processing  status=done
progress=10      progress=50,90     progress=100
```

При любой ошибке — `status=failed` + `refund_gems`.

---

## Таблица всех API эндпоинтов

### Публичные (без авторизации)

| Метод | Путь | Auth | Описание | Входные параметры | Ответ |
|-------|------|------|----------|-------------------|-------|
| GET | `/health` | — | Healthcheck | — | `{"status": "ok"}` |
| POST | `/v1/auth/register` | — | Регистрация | `{email, password}` | `{user, access_token, refresh_token}` |
| POST | `/v1/auth/login` | — | Вход | `{email, password}` | `{access_token, refresh_token, token_type}` |
| POST | `/v1/auth/refresh` | — | Обновить токен | `{refresh_token}` | `{access_token}` |
| GET | `/v1/templates` | — | Список шаблонов | `?category&trending&page&per_page` | `{items[], total}` |
| GET | `/v1/templates/{id}` | — | Детали шаблона (+ plays++) | path: `template_id` | `TemplateDetail` |
| GET | `/v1/categories` | — | Список категорий | — | `[CategoryOut]` |
| GET | `/v1/gem-packages` | — | Список пакетов гемов | — | `{items[]}` |
| GET | `/v1/subscription-plans` | — | Список подписок | — | `{items[]}` |
| GET | `/v1/config/onboarding-video` | — | URL онбординг-видео | — | `{"url": str\|null}` |
| POST | `/v1/reports` | Optional JWT | Отправить жалобу на шаблон | `{template_id, reason, description?}` | `{"id", "status": "received"}` |
| POST | `/v1/payments/webhook` | Header `x-signature` (не проверяется) | Webhook пополнения гемов | `{user_id, gems_amount, product_id, payment_id}` | `{"success": true}` |

### Авторизованные пользователи (`Authorization: Bearer <token>`)

| Метод | Путь | Auth | Описание | Входные параметры | Ответ |
|-------|------|------|----------|-------------------|-------|
| GET | `/v1/auth/me` | JWT | Текущий пользователь | — | `{id, email, gems, subscription_status}` |
| POST | `/v1/jobs` | JWT | Создать джоб (генерация видео) | `{template_id, options?, quality?, duration_seconds?}` | `{job_id, status, gems_cost}` |
| GET | `/v1/jobs` | JWT | Список джобов пользователя | — | `{items[], total}` |
| GET | `/v1/jobs/{id}` | JWT | Статус джоба | path: `job_id` | `{status, progress, result_url, error}` |
| GET | `/v1/me/gems` | JWT | Баланс гемов | — | `{gems, subscription_status, subscription_expires_at, subscription_active}` |
| POST | `/v1/me/daily-bonus` | JWT | Получить ежедневный бонус | — | `{gems_awarded, new_balance}` |
| GET | `/v1/me/transactions` | JWT | История транзакций | `?page&per_page` | `{items[], total}` |

### Admin (`Authorization: Bearer <admin_token>`, `role=admin`)

#### Templates

| Метод | Путь | Описание | Параметры |
|-------|------|----------|-----------|
| GET | `/v1/admin/templates` | Список всех шаблонов | `?page&per_page&search` |
| POST | `/v1/admin/templates` | Создать шаблон | form-data: `title, description?, likes, plays, gems_cost, photo_slots, has_male_slot, has_female_slot, video?, thumb?` |
| PUT | `/v1/admin/templates/{id}` | Обновить шаблон | form-data: любые поля + video? + thumb? |
| DELETE | `/v1/admin/templates/{id}` | Удалить шаблон | — |
| POST | `/v1/admin/templates/{id}/reprocess` | Перегенерировать thumb/preview/gif | — |
| POST | `/v1/admin/templates/reprocess-all` | Перегенерировать для всех без thumb | — |
| POST | `/v1/admin/templates/reprocess-compressed` | Создать preview_small для шаблонов без него | — |

#### Categories

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/v1/admin/categories` | Список категорий |
| POST | `/v1/admin/categories` | Создать категорию |
| PUT | `/v1/admin/categories/{id}` | Обновить категорию |
| DELETE | `/v1/admin/categories/{id}` | Удалить категорию |
| GET | `/v1/admin/categories/{id}/templates` | Шаблоны в категории |
| POST | `/v1/admin/categories/{id}/templates` | Добавить шаблоны в категорию |
| DELETE | `/v1/admin/categories/{id}/templates/{tid}` | Убрать шаблон из категории |
| PATCH | `/v1/admin/categories/{id}/templates/{tid}/order` | Изменить порядок шаблона |

#### Trends, Users, Jobs, Reports

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/v1/admin/trends` | Список трендов |
| POST | `/v1/admin/trends` | Добавить тренд |
| PUT | `/v1/admin/trends/{id}` | Обновить тренд |
| DELETE | `/v1/admin/trends/{id}` | Удалить тренд |
| GET | `/v1/admin/users` | Список пользователей с фильтрами (`?search&subscription&is_banned&page&per_page`) |
| GET | `/v1/admin/users/{id}` | Профиль пользователя |
| POST | `/v1/admin/users/{id}/gems` | Скорректировать баланс гемов |
| PUT | `/v1/admin/users/{id}/subscription` | Изменить подписку |
| POST | `/v1/admin/users/{id}/ban` | Забанить пользователя |
| POST | `/v1/admin/users/{id}/unban` | Разбанить |
| GET | `/v1/admin/users/{id}/transactions` | История транзакций пользователя |
| GET | `/v1/admin/jobs` | Все джобы (`?status&page&per_page`) |
| GET | `/v1/admin/reports` | Жалобы (`?status&template_id&page&per_page`) |
| PUT | `/v1/admin/reports/{id}` | Обновить статус жалобы |

#### Config, Pricing, Gem Packages, Subscription Plans, Stats

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/v1/admin/config/stub` | Настройки stub режима |
| PUT | `/v1/admin/config/stub` | Обновить stub настройки |
| GET | `/v1/admin/config/models` | AI endpoint/token |
| PUT | `/v1/admin/config/models` | Обновить AI endpoint/token |
| GET | `/v1/admin/config/onboarding-video` | URL онбординг-видео |
| POST | `/v1/admin/config/onboarding-video` | Загрузить онбординг-видео |
| DELETE | `/v1/admin/config/onboarding-video` | Удалить онбординг-видео |
| GET | `/v1/admin/pricing` | Настройки ценообразования |
| PUT | `/v1/admin/pricing` | Обновить ценообразование |
| GET | `/v1/admin/gem-packages` | Все пакеты гемов |
| POST | `/v1/admin/gem-packages` | Создать пакет |
| PUT | `/v1/admin/gem-packages/{id}` | Обновить пакет |
| DELETE | `/v1/admin/gem-packages/{id}` | Удалить пакет |
| GET | `/v1/admin/subscription-plans` | Все планы подписок |
| POST | `/v1/admin/subscription-plans` | Создать план |
| PUT | `/v1/admin/subscription-plans/{id}` | Обновить план |
| DELETE | `/v1/admin/subscription-plans/{id}` | Удалить план |
| GET | `/v1/admin/audit-log` | Лог аудита (`?page&per_page`) |
| GET | `/v1/admin/stats/gems` | Статистика гемов (сегодня) |
| POST | `/v1/admin/stub/test-job` | Создать тестовый джоб |

---

## Модели данных

### `users`

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID PK | |
| email | VARCHAR(255) UNIQUE NOT NULL | |
| password_hash | VARCHAR(255) NOT NULL | bcrypt |
| role | VARCHAR(20) default="user" | "user" \| "admin" |
| gems | INTEGER default=0 | Баланс внутренней валюты |
| subscription_status | VARCHAR(20) default="free" | "free" \| "vip" \| "svip" |
| subscription_expires_at | DATETIME nullable | |
| is_banned | BOOLEAN default=false | |
| google_id | VARCHAR(255) nullable | |
| apple_id | VARCHAR(255) nullable | |
| name | VARCHAR(255) nullable | |
| last_daily_bonus_at | DATETIME nullable | |
| referral_code | VARCHAR(20) UNIQUE nullable | |
| referred_by | UUID nullable | |
| created_at | DATETIME server_default=now() | |

### `templates`

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID PK | |
| title | VARCHAR(255) NOT NULL | |
| description | TEXT | |
| video_path | VARCHAR(500) | Путь в R2 bucket=templates |
| thumb_path | VARCHAR(500) | Миниатюра |
| gif_path | VARCHAR(500) | GIF-превью (3 сек, 480px) |
| preview_path | VARCHAR(500) | Полное превью (15 сек, 720p) |
| preview_compressed_path | VARCHAR(500) | Сжатое превью (6 сек, 360p) |
| status | VARCHAR(20) default="ready" | "ready" \| "processing" \| "failed" \| "queued" |
| likes | INTEGER default=0 | |
| plays | INTEGER default=0 | Инкрементируется при GET detail |
| is_active | BOOLEAN default=true | |
| gems_cost | INTEGER default=200 | |
| photo_slots | INTEGER default=1 | Количество слотов для фото |
| has_male_slot | BOOLEAN default=false | |
| has_female_slot | BOOLEAN default=false | |
| created_by | UUID FK→users.id | |
| created_at | DATETIME server_default=now() | |

### `jobs`

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID PK | |
| user_id | UUID FK→users.id | |
| template_id | UUID FK→templates.id ON DELETE SET NULL | |
| status | VARCHAR(20) default="queued" | "queued" \| "processing" \| "done" \| "failed" |
| progress | INTEGER default=0 | 0–100 |
| result_path | VARCHAR(500) | Signed URL готового видео |
| error | TEXT | Описание ошибки |
| options | JSONB | `{quality?, orientation?, prompt?, photo_url?, photo_url_male?, photo_url_female?}` |
| gems_cost | INTEGER default=0 | Стоимость при создании |
| quality | VARCHAR(20) default="standard" | "standard" \| "hd" \| "ultra_hd" |
| duration_seconds | INTEGER default=10 | |
| created_at | DATETIME server_default=now() | |
| updated_at | DATETIME server_default=now() onupdate=now() | |

### `categories`

| Поле | Тип | |
|------|-----|-|
| id | UUID PK | |
| name | VARCHAR(100) NOT NULL | |
| order | INTEGER default=0 | |

### `category_templates` (M2M)

| Поле | Тип | |
|------|-----|-|
| category_id | UUID FK→categories.id | PK composite |
| template_id | UUID FK→templates.id CASCADE | PK composite |
| order | INTEGER default=0 | Порядок в категории |

### `gem_packages`

| Поле | Тип | |
|------|-----|-|
| id | UUID PK | |
| gems_amount | INTEGER NOT NULL | Основное количество гемов |
| bonus_gems | INTEGER default=0 | |
| price | NUMERIC(10,2) NOT NULL | |
| currency | VARCHAR(10) default="UAH" | |
| label | VARCHAR(100) | |
| is_popular | BOOLEAN default=false | |
| is_active | BOOLEAN default=true | |
| apple_product_id | VARCHAR(200) | |
| google_product_id | VARCHAR(200) | |
| order | INTEGER default=0 | |

### `gem_transactions`

| Поле | Тип | |
|------|-----|-|
| id | UUID PK | |
| user_id | UUID FK→users.id NOT NULL | |
| amount | INTEGER NOT NULL | Отрицательное при списании |
| balance_after | INTEGER NOT NULL | Баланс после операции |
| type | VARCHAR(50) NOT NULL | "purchase" \| "generation" \| "refund" \| "admin_adjustment" \| "bonus" |
| description | TEXT | |
| reference_id | VARCHAR(255) | ID платежа или джоба |
| created_at | DATETIME server_default=now() | |

### `subscription_plans`

| Поле | Тип | |
|------|-----|-|
| id | UUID PK | |
| name | VARCHAR(100) | |
| tier | VARCHAR(20) | "free" \| "vip" \| "svip" |
| period | VARCHAR(20) | "monthly" \| "yearly" |
| price | NUMERIC(10,2) | |
| currency | VARCHAR(10) default="UAH" | |
| bonus_gems | INTEGER default=0 | |
| discount_percent | INTEGER default=0 | |
| apple_product_id | VARCHAR(200) | |
| google_product_id | VARCHAR(200) | |
| is_active | BOOLEAN default=true | |
| order | INTEGER default=0 | |

### `trends`

| Поле | Тип | |
|------|-----|-|
| id | UUID PK | |
| template_id | UUID FK→templates.id | |
| order | INTEGER default=0 | |

### `reports`

| Поле | Тип | |
|------|-----|-|
| id | UUID PK | |
| template_id | UUID FK→templates.id CASCADE NOT NULL | |
| user_id | UUID FK→users.id nullable | |
| reason | VARCHAR(100) NOT NULL | |
| description | TEXT | |
| status | VARCHAR(20) default="pending" | "pending" \| "reviewed" \| "dismissed" |
| created_at | DATETIME server_default=now() | |

### `admin_config`

| Поле | Тип | |
|------|-----|-|
| key | VARCHAR(100) PK | |
| value | TEXT | |
| updated_at | DATETIME | |
| updated_by | UUID FK→users.id nullable | |

Ключи: `STUB_MODE`, `STUB_LATENCY_MS`, `STUB_SUCCESS_RATE`, `AI_ENDPOINT`, `AI_TOKEN`, `ONBOARDING_VIDEO`, `GEMS_DAILY_BONUS`, `GEMS_BASE_PER_5S`, `GEMS_BASE_PER_10S`, `GEMS_MULTIPLIER_STANDARD`, `GEMS_MULTIPLIER_HD`, `GEMS_MULTIPLIER_ULTRA_HD`

### `audit_log`

| Поле | Тип | |
|------|-----|-|
| id | UUID PK | |
| user_id | UUID FK→users.id nullable | |
| action | VARCHAR(100) | "create" \| "update" \| "delete" |
| entity | VARCHAR(100) | "template" |
| entity_id | VARCHAR(100) | |
| details | JSONB | |
| created_at | DATETIME server_default=now() | |

---

## Схема БД (связи)

```
users ─────────────────────────────────┐
  │                                    │
  ├──< jobs (user_id)                  │
  │     └── templates (template_id)    │
  │                                    │
  ├──< gem_transactions (user_id)      │
  │                                    │
  └──< reports (user_id nullable)      │
                                       │
templates ──< category_templates       │
  │             └── categories         │
  ├──< trends                          │
  └──< reports (template_id)           │
                                       │
admin_config (updated_by) ────────────┘
audit_log (user_id) ──────────────────┘
```

---

## Аутентификация и авторизация

### JWT Flow
1. `POST /v1/auth/register` или `/v1/auth/login` → получаем `access_token` (HS256 JWT, 30 дней) + `refresh_token` (30 дней).
2. Все защищённые эндпоинты требуют заголовок: `Authorization: Bearer <access_token>`.
3. `POST /v1/auth/refresh` → новый `access_token` по `refresh_token`.

### Middleware авторизации (`core/dependencies.py`)
- `get_current_user` — декодирует JWT, загружает `User`, проверяет `is_banned`, авто-сбрасывает подписку если истекла.
- `get_admin_user` — вызывает `get_current_user` + проверяет `user.role == "admin"`.

### Роли
- `user` — стандартный пользователь.
- `admin` — доступ ко всем `/v1/admin/*` эндпоинтам.

---

## Система гемов

Гемы — внутренняя валюта. Все операции — через `services/gems.py`:

| Операция | Функция | Описание |
|----------|---------|----------|
| Списание | `deduct_gems()` | При создании джоба. HTTP 402 если недостаточно. |
| Начисление | `add_gems()` | Покупка, бонус, admin adjustment |
| Возврат | `refund_gems()` | При failed джобе (авто) |
| SVIP скидка | `apply_svip_discount()` | 50% скидка для активных SVIP |
| Daily bonus | `/v1/me/daily-bonus` | Базовый бонус × 2 для SVIP (cooldown 24ч) |

---

## Фоновые задачи (Workers)

### Pipeline генерации видео

```
POST /v1/jobs
  → deduct_gems()
  → Job(status="queued")
  → publish_job() → RabbitMQ [jobs.preproc]
         │
         ▼ preproc_worker
  status=processing, progress=10
  Создаёт thumb-заглушку → [jobs.generator]
         │
         ▼ generator_worker
  progress=50 → sleep(latency_ms) → progress=90
  stub: copy mock_result.mp4 → results bucket → [jobs.postproc]
  fail: refund_gems()
         │
         ▼ postproc_worker
  presigned_url (24ч) → job.result_path=URL
  status=done, progress=100
```

### Pipeline обработки шаблонов

```
POST /v1/admin/templates (с video) OR /reprocess
  → publish() → RabbitMQ [templates.thumbnail]
         │
         ▼ thumbnail_worker
  download video from R2
  FFmpeg: preview_small.mp4 (360p, 6s, CRF35)
          preview.mp4 (720p, 15s)
          preview.gif (480px, 3s, 10fps)
          thumb.jpg (first frame)
  upload all → templates bucket
  template.status = "ready"
```

### Очереди RabbitMQ

| Очередь | Воркер | Назначение |
|---------|--------|------------|
| `jobs.preproc` | `preproc_worker` | Предобработка джоба |
| `jobs.generator` | `generator_worker` | Генерация видео (AI/stub) |
| `jobs.postproc` | `postproc_worker` | Постобработка, signed URL |
| `jobs.dlq` | — | Dead letter queue |
| `templates.thumbnail` | `thumbnail_worker` | FFmpeg обработка шаблонов |

---

## Cloudflare R2 / Хранилище файлов

### Buckets

| Bucket | Доступ | Содержимое |
|--------|--------|-----------|
| `uploads` | Приватный | Временные загрузки пользователей; доступ через presigned URL |
| `results` | Приватный | Готовые видео: `{job_id}/output.mp4`, превью, thumb; presigned URL 7 дней |
| `templates` | Публичный | Файлы шаблонов: `templates/{id}/original.mp4`, `thumb.jpg`, `preview.mp4`, `preview_small.mp4`, `preview.gif`, `mock_result.mp4`, `onboarding/background.mp4` |

### URL формирование
- Шаблоны (публичный bucket): `{R2_PUBLIC_URL_TEMPLATES}/{path}` — без имени бакета в пути
- Uploads и results (приватные): presigned GET через `get_signed_url()`, срок 7 дней
- Presigned URLs хранятся в БД (поля `result_path`, `preview_url`, `thumb_url`, `original_url`)

---

## Обработка ошибок

| HTTP код | Когда возникает |
|----------|----------------|
| 400 | Email уже зарегистрирован, нельзя забанить admin, duplicate webhook |
| 401 | Invalid/expired JWT, неверный пароль |
| 402 | Insufficient gems |
| 403 | is_banned=true, требуется admin |
| 404 | User/Template/Job/Category/Report не найден |
| 422 | Ошибка валидации Pydantic (автоматически FastAPI) |

Формат ошибки (FastAPI default):
```json
{"detail": "Error message"}
```

Ошибка валидации (422):
```json
{
  "detail": [
    {"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error.email"}
  ]
}
```

---

## CORS

Разрешённые origins (только localhost для разработки):
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

`allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`

> Для production необходимо добавить реальные origins.
