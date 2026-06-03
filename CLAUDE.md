# Trimvo Backend — CLAUDE.md

## Project Context

Trimvo — бэкенд мобильного приложения для генерации видео на основе шаблонов. Пользователи тратят гемы (внутренняя валюта) на генерацию; видео создаётся асинхронно через pipeline из 3 RabbitMQ воркеров. Стек: FastAPI + SQLAlchemy (sync) + PostgreSQL + RabbitMQ + MinIO + React Admin UI. Проект находится в стадии MVP — AI генерация заменена stub-заглушкой.

Весь код бэкенда находится в `api/`. Рабочая директория для большинства команд — `api/` или корень проекта.

---

## Quick Start

```bash
# Запуск всего стека (рекомендуется)
cd ~/Desktop/beckend_trimvo
cp .env.example .env          # если .env ещё нет
docker compose up --build

# API:        http://localhost:8000
# Admin UI:   http://localhost:3000
# MinIO:      http://localhost:9001 (minioadmin/minioadmin)
# RabbitMQ:   http://localhost:15672 (guest/guest)

# Загрузить тестовые данные
docker compose exec api python seed.py

# Остановить
docker compose down

# Остановить + удалить данные
docker compose down -v
```

```bash
# Применить миграции вручную
docker compose exec api alembic upgrade head

# Создать новую миграцию
docker compose exec api alembic revision --autogenerate -m "describe_change"

# Просмотр логов
docker compose logs api --tail 50 -f
docker compose logs worker-generator --tail 50 -f

# Подключиться к PostgreSQL
docker compose exec postgres psql -U postgres -d trimvo

# Диагностика битых шаблонов
docker compose exec api python check_broken_templates.py

# Проверить файлы в MinIO
docker compose exec api python check_minio_files.py
```

---

## Key Files Map

| Задача | Файлы для изменения |
|--------|---------------------|
| Добавить публичный эндпоинт | `api/routers/{resource}.py`, зарегистрировать в `api/main.py` |
| Добавить admin эндпоинт | `api/routers/admin/{resource}.py`, зарегистрировать в `api/main.py` |
| Добавить/изменить модель БД | `api/models/{model}.py`, создать миграцию `alembic revision --autogenerate` |
| Изменить схему ответа/запроса | `api/schemas/{resource}.py` |
| Изменить логику гемов | `api/services/gems.py` |
| Изменить pipeline генерации | `api/workers/preproc_worker.py`, `generator_worker.py`, `postproc_worker.py` |
| Изменить обработку шаблонов | `api/workers/thumbnail_worker.py`, `api/services/media_processor.py` |
| Изменить работу с файлами | `api/services/storage.py` |
| Добавить настройку конфига | `api/models/admin_config.py` (новый ключ), `api/routers/admin/config.py` |
| Изменить JWT/auth логику | `api/core/security.py`, `api/core/dependencies.py` |
| Изменить переменные окружения | `api/core/config.py` (добавить поле), `.env.example` |
| Добавить в очередь | `api/services/queue.py` (новая константа + publish) |

---

## Architecture Rules

**Обязательно соблюдать:**

1. **Никакой бизнес-логики в роутерах** — роутеры только валидируют входные данные и вызывают сервисы. Исключение: простые CRUD без логики.

2. **Операции с гемами — только через `services/gems.py`** — никогда не изменяй `user.gems` напрямую в роутерах или воркерах без записи в `gem_transactions`.

3. **Все входящие данные валидируются через Pydantic схемы** — не принимай `dict` без схемы.

4. **Ошибки — только через `HTTPException`** в роутерах, стандартный Python exception в воркерах (логируется).

5. **Admin роутеры — только через `get_admin_user`** — никогда не используй `get_current_user` там где нужен admin.

6. **Аудит-лог для критичных admin операций** — при изменении/создании/удалении шаблонов вызывай `_audit()` (пример в `routers/admin/templates.py`).

7. **Воркеры всегда закрывают DB-сессию** — паттерн: `db = SessionLocal()` → `try/finally: db.close()`.

8. **Воркеры всегда возвращают гемы при ошибке** — если `job.gems_cost > 0` и `status=failed` → `refund_gems()`.

9. **MinIO пути** — в БД хранятся пути без bucket-префикса и без ведущего слэша: `templates/uuid/thumb.jpg`. URL строится через `_pub()` или `_public_url()` функции в роутерах.

10. **Stub mode контролируется через `AdminConfig`**, не через `.env` напрямую — воркеры читают из БД при каждом джобе.

---

## Code Style

**Именование**:
- Файлы: `snake_case.py`
- Классы ORM: `PascalCase` (совпадает с именем таблицы в единственном числе: `User`, `Template`, `Job`)
- Pydantic схемы: `PascalCase` + суффикс `Out`/`Create`/`Update`/`Response`
- Функции: `snake_case`
- Переменные: `snake_case`

**Структура нового роутера**:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.dependencies import get_current_user  # или get_admin_user

router = APIRouter(prefix="/v1/{resource}", tags=["{resource}"])

@router.get("", response_model=SomeListResponse)
def list_items(db: Session = Depends(get_db)):
    ...

@router.post("", response_model=SomeOut)
def create_item(body: SomeCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ...
```

**Регистрация нового роутера** — добавить в `api/main.py`:
```python
from routers import new_router
app.include_router(new_router.router)
```

**Структура нового воркера**:
```python
def process_item(item_id: str):
    db = SessionLocal()
    try:
        ...
    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    while True:
        try:
            # подключиться к RabbitMQ, начать consume
            ...
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 5s")
            time.sleep(5)
```

---

## Common Tasks

```bash
# Создать миграцию после изменения models/
docker compose exec api alembic revision --autogenerate -m "add_field_to_users"
docker compose exec api alembic upgrade head

# Откатить последнюю миграцию
docker compose exec api alembic downgrade -1

# Пересборка образов (после изменения requirements.txt)
docker compose up --build api

# Посмотреть логи конкретного воркера
docker compose logs worker-thumbnail -f

# Запустить seed для тестовых данных
docker compose exec api python seed.py

# Прямой SQL запрос
docker compose exec postgres psql -U postgres -d trimvo -c "SELECT * FROM users LIMIT 5;"

# Проверить статусы джобов
docker compose exec postgres psql -U postgres -d trimvo -c "SELECT status, count(*) FROM jobs GROUP BY status;"

# Принудительно пересгенерировать превью всех шаблонов без thumb
curl -X POST http://localhost:8000/v1/admin/templates/reprocess-all \
  -H "Authorization: Bearer <admin_token>"
```

---

## Environment

Переменные, **обязательные** для локальной разработки (минимальный `.env`):

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/trimvo
REDIS_URL=redis://redis:6379
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_PUBLIC_URL=http://localhost:9000
JWT_SECRET=dev-secret-change-in-production
```

> **КРИТИЧНО**: `MINIO_PUBLIC_URL` должен быть `http://localhost:9000` (не `minio:9000`), иначе браузер не сможет открыть URL файлов.

---

## Do Not Touch

| Путь | Причина |
|------|---------|
| `api/alembic/versions/` | Автогенерированные миграции. Редактируй только если миграция ещё не применена. |
| `api/alembic/env.py` | Стандартный Alembic env, не изменять без нужды. |
| `.env` | Секреты. Никогда не коммитить. |
| `admin/node_modules/` | NPM зависимости, не трогать вручную. |
| `api/workers/Dockerfile` | Образ воркеров, менять только при добавлении системных зависимостей. |

---

## Связанный фронтенд

Этот бэкенд обслуживает **Flutter-приложение Trimvo**.

При изменении любого эндпоинта **обязательно проверяй совместимость** с:
- `ARCHITECTURE.md` фронтенда (раздел API Endpoints)
- Модели данных должны соответствовать Flutter-моделям:
  - `TemplateModel` ← `TemplateOut` / `TemplateDetail`
  - `JobModel` ← `JobOut` / `JobStatusResponse`
  - `AuthState` ← `RegisterResponse` / `TokenResponse`
  - `GemPackage` ← `GemPackageOut`
  - `SubscriptionPlan` ← `SubscriptionPlanOut`

**Особо критичные для фронтенда поля**:
- `TemplateOut.preview_compressed_url` — используется в карточках списка
- `JobStatusResponse.result_url` — URL готового видео (presigned, истекает через 24ч)
- `UserOut.gems` и `subscription_status` — отображаются везде

---

## Документация

- `PROJECT.md` — Tech stack, структура, запуск, env, известные проблемы
- `ARCHITECTURE.md` — Слои, все эндпоинты, модели БД, workers pipeline
- `API_RULES.md` — Конвенции, форматы, коды ошибок, auth
- `CLAUDE.md` — Этот файл, инструкция для AI-ассистента
