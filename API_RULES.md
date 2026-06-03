# Trimvo — API Rules & Conventions

## Конвенции именования

- **Префикс**: все эндпоинты начинаются с `/v1/`
- **Стиль путей**: kebab-case (`/gem-packages`, `/subscription-plans`, `/daily-bonus`)
- **Admin эндпоинты**: `/v1/admin/{resource}`
- **Параметры запроса**: snake_case (`?per_page`, `?is_banned`)
- **Тела запросов (JSON)**: snake_case (`template_id`, `gems_amount`)
- **Имена файлов в коде**: snake_case (`gem_packages.py`, `subscription_plan.py`)

---

## Формат ответов

### Успешный ответ (список с пагинацией)

```json
{
  "items": [...],
  "total": 42
}
```

### Успешный ответ (объект)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "progress": 100,
  "result_url": "https://account.r2.cloudflarestorage.com/results/...?X-Amz-...",
  "error": null
}
```

### Успешная операция без данных

```json
{"success": true}
```

### Ошибка (все HTTP 4xx/5xx)

```json
{"detail": "Error message string"}
```

### Ошибка валидации (422 Unprocessable Entity)

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Коды ошибок

| HTTP статус | Когда возникает | Пример detail |
|-------------|----------------|---------------|
| 400 Bad Request | Email уже занят, нельзя забанить admin, дублирующий webhook, неверный статус жалобы | `"Email already registered"` |
| 401 Unauthorized | Невалидный/просроченный JWT, неверный пароль | `"Invalid token"`, `"Invalid credentials"` |
| 402 Payment Required | Недостаточно гемов | `"Insufficient gems. Required: 200, available: 50"` |
| 403 Forbidden | Аккаунт забанен, недостаточно прав (не admin) | `"Account is banned"`, `"Admin access required"` |
| 404 Not Found | Ресурс не найден | `"Template not found"`, `"User not found"` |
| 422 Unprocessable Entity | Ошибка валидации тела запроса (Pydantic) | см. формат выше |

---

## Пагинация

**Стиль**: page + per_page (offset-based).

**Параметры запроса**:
- `page` — номер страницы (default=1, ge=1)
- `per_page` — элементов на страницу (default=20, ge=1, le=100)

**Ответ**:
```json
{
  "items": [...],
  "total": 123
}
```

**Используется в**:
- `GET /v1/templates?page=1&per_page=20`
- `GET /v1/me/transactions?page=1&per_page=20`
- `GET /v1/admin/users?page=1&per_page=20`
- `GET /v1/admin/jobs?page=1&per_page=50`
- `GET /v1/admin/reports?page=1&per_page=20`
- `GET /v1/admin/audit-log?page=1&per_page=50`

---

## Аутентификация

**Тип**: Bearer Token (JWT HS256)

**Заголовок**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

**Получение токена**:
```
POST /v1/auth/login
Body: {"email": "user@example.com", "password": "secret"}
Response: {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

**Обновление**:
```
POST /v1/auth/refresh
Body: {"refresh_token": "..."}
Response: {"access_token": "..."}
```

**Время жизни**:
- Access token: 43200 минут (30 дней, настраивается `JWT_EXPIRE_MINUTES`)
- Refresh token: 30 дней (настраивается `REFRESH_TOKEN_EXPIRE_DAYS`)

**JWT payload**:
```json
{"sub": "<user_uuid>", "exp": <timestamp>, "type": "access"|"refresh"}
```

**Необязательная авторизация**: `POST /v1/reports` — принимает токен если есть, но работает и без него (анонимная жалоба).

---

## Валидация

**Библиотека**: Pydantic v2

**Входные данные**:
- Все тела JSON-запросов валидируются через Pydantic схемы (файлы `api/schemas/*.py`)
- Загрузка файлов: `UploadFile` + `Form` (multipart/form-data)
- Поля типа `UUID` — строгая типизация
- Email — `EmailStr` (только в `/v1/auth/register` и `/v1/auth/login`)

**При ошибке валидации**: HTTP 422 с полным описанием проблемы.

**Важно**: поле `reason` в `ReportCreate` не валидируется против `VALID_REASONS` (определён в `schemas/report.py`, но не применяется).

---

## Загрузка файлов

**Эндпоинты с загрузкой**: `multipart/form-data`
- `POST /v1/admin/templates` — поля `video` (mp4) и `thumb` (jpg)
- `PUT /v1/admin/templates/{id}` — те же поля опционально
- `POST /v1/admin/config/onboarding-video` — поле `video` (mp4 или gif)

**Хранилище**: Cloudflare R2 bucket `templates` (публичный)

**Ключи объектов**:
- Видео: `templates/{template_id}/original.mp4`
- Кастомная миниатюра: `templates/{template_id}/thumb_custom.jpg`
- Сгенерированные превью: `templates/{template_id}/preview.mp4`, `preview_small.mp4`, `preview.gif`, `thumb.jpg`
- Онбординг: `onboarding/background.mp4` (или `.gif`)

**Публичные URL**: `{R2_PUBLIC_URL_TEMPLATES}/{path}` (bucket `templates`, без имени бакета в пути)
После загрузки видео шаблона автоматически ставится в очередь `templates.thumbnail` для генерации превью.

---

## Rate Limiting

Не реализован. Redis подключён в зависимостях, но rate limiting не применяется ни к одному эндпоинту.

---

## CORS

Разрешено только с `localhost:3000` и `localhost:5173`. Для production необходимо изменить `allow_origins` в `api/main.py`.

---

## Версионирование API

Все эндпоинты имеют префикс `/v1/`. Версии `/v2/` не существует. При смене версии необходимо добавлять новые роутеры с новым префиксом.

---

## Особенности и нюансы

### Plays counter
`GET /v1/templates/{id}` автоматически инкрементирует `template.plays`. Каждый просмотр детальной страницы — это +1. Не идемпотентно.

### Job result URL
`job.result_path` после завершения содержит не путь, а presigned URL (24 часа). Клиент должен обновлять/переполучать URL перед воспроизведением.

### Gems deduct on job create
Гемы списываются **сразу** при `POST /v1/jobs`. Если публикация в очередь не удалась — авто-возврат. Если воркер упал — возврат в воркере. Нет гарантии возврата при краше после деbit но до refund.

### Дублирование webhook
`POST /v1/payments/webhook` — идемпотентный: повторный запрос с тем же `payment_id` возвращает `{"success": true, "duplicate": true}` без начисления гемов.

### Admin first user
Первый admin создаётся через `seed.py` или вручную в БД. Обычная регистрация создаёт только `role=user`.
