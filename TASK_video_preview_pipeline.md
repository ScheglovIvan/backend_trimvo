# TASK: Pipeline превью для сгенерированных видео + автовоспроизведение в History

## Контекст

Проект бэкенд: `~/Desktop/beckend_hyper_cut`
Проект фронтенд: `~/Desktop/hyper_cut`

Сейчас `postproc_worker` просто строит прямой URL на оригинальный `.mp4` от Replicate
и сохраняет его в `job.result_path`. Задача:

1. **Бэкенд**: скачать оригинал → сохранить в MinIO → создать превью/тамб через FFmpeg → сохранить пути в БД
2. **Фронтенд**: в History показывать превью-видео с автовоспроизведением, в полном просмотре — оригинал + скачать/поделиться

---

# ЧАСТЬ 1 — БЭКЕНД

## Шаг Б1 — Добавить поля в модель Job

Открыть `api/models/job.py`.

Найти блок колонок (после `result_path`) и добавить новые поля:

```python
# после строки: result_path = Column(String(500))
preview_url      = Column(String(500))   # превью для карточек (360p, лёгкое)
thumb_url        = Column(String(500))   # первый кадр как jpg
original_url     = Column(String(500))   # оригинальное видео (полное качество)
```

## Шаг Б2 — Создать миграцию

```bash
cd ~/Desktop/beckend_hyper_cut
docker compose exec api alembic revision --autogenerate -m "add_preview_fields_to_jobs"
docker compose exec api alembic upgrade head
```

Проверить что миграция применилась:
```bash
docker compose exec postgres psql -U postgres -d hypercut \
  -c "\d jobs" | grep -E "preview_url|thumb_url|original_url"
# должны появиться 3 строки
```

## Шаг Б3 — Обновить схему JobOut

Открыть `api/schemas/job.py`.

В класс `JobOut` добавить три поля после `result_path`:

```python
preview_url:   Optional[str] = None
thumb_url:     Optional[str] = None
original_url:  Optional[str] = None
```

В класс `JobStatusResponse` добавить:

```python
preview_url:  Optional[str] = None
thumb_url:    Optional[str] = None
original_url: Optional[str] = None
```

## Шаг Б4 — Переписать postproc_worker.py

Полностью заменить содержимое `api/workers/postproc_worker.py`:

```python
"""Post-processing worker: download result, generate previews, mark job done."""
import sys
import os
import json
import time
import logging
import tempfile

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pika

from core.config import get_settings
from core.database import SessionLocal
from models.job import Job
from models.user import User
from services.storage import get_client, settings as storage_settings, ensure_buckets
from services.media_processor import process_video
from services.gems import refund_gems
from services.queue import QUEUE_POSTPROC, QUEUE_DLQ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("postproc_worker")

settings = get_settings()


def _public_url(bucket: str, key: str) -> str:
    base = settings.minio_public_url.rstrip("/")
    return f"{base}/{bucket}/{key}"


def _download_bytes(url: str) -> bytes:
    """Download file from URL, return bytes."""
    logger.info(f"Downloading: {url[:80]}...")
    resp = requests.get(url, timeout=180, stream=True)
    resp.raise_for_status()
    chunks = []
    for chunk in resp.iter_content(chunk_size=65536):
        chunks.append(chunk)
    data = b"".join(chunks)
    logger.info(f"Downloaded {len(data) // 1024} KB")
    return data


def _save_original(job_id: str, video_bytes: bytes, fmt: str = "mp4") -> str:
    """Upload original video to MinIO, return key."""
    key = f"results/{job_id}/original.{fmt}"
    client = get_client()
    import io
    client.put_object(
        storage_settings.minio_bucket_results,
        key,
        io.BytesIO(video_bytes),
        length=len(video_bytes),
        content_type=f"video/{fmt}",
    )
    logger.info(f"Saved original to MinIO: {key}")
    return key


def process_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        if not job.result_path:
            job.status = "failed"
            job.error = "No result path set by generator"
            db.commit()
            return

        result_path = job.result_path
        logger.info(f"Job {job_id}: postproc started, result_path={result_path[:80]}...")

        # ── 1. Скачать оригинал ──────────────────────────────────────────────
        # result_path может быть:
        # а) MinIO key: "results/uuid/output.mp4"
        # б) HTTP URL от Replicate: "https://replicate.delivery/..."
        # б) Уже полный MinIO URL: "http://10.x.x.x:9000/results/..."

        video_bytes = None
        original_key = None

        if result_path.startswith("http"):
            # Скачиваем с внешнего URL (Replicate) или уже с нашего MinIO
            video_bytes = _download_bytes(result_path)
            fmt = "mp4"
            if result_path.endswith(".mov"):
                fmt = "mov"
            original_key = _save_original(job_id, video_bytes, fmt)
        else:
            # Уже в MinIO — скачиваем оттуда
            client = get_client()
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                client.fget_object(
                    storage_settings.minio_bucket_results,
                    result_path,
                    tmp_path,
                )
                with open(tmp_path, "rb") as f:
                    video_bytes = f.read()
                original_key = result_path  # уже сохранён
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        if not video_bytes:
            raise RuntimeError("Failed to obtain video bytes")

        # ── 2. Генерировать превью через FFmpeg ──────────────────────────────
        base_key = f"results/{job_id}"
        logger.info(f"Job {job_id}: generating previews via FFmpeg...")

        media_result = process_video(
            video_bytes,
            base_key,
            storage_settings.minio_bucket_results,
        )
        # media_result содержит: preview_compressed_path, preview_path, gif_path, thumb_path

        # ── 3. Сохранить все пути в БД ───────────────────────────────────────
        bucket = storage_settings.minio_bucket_results

        # Оригинал
        job.original_url = _public_url(bucket, original_key)

        # Превью для карточек (360p, лёгкое)
        if media_result.get("preview_compressed_path"):
            job.preview_url = _public_url(bucket, media_result["preview_compressed_path"])

        # Тамб (первый кадр)
        if media_result.get("thumb_path"):
            job.thumb_url = _public_url(bucket, media_result["thumb_path"])

        # result_path — для обратной совместимости ставим превью
        # (фронт читает result_path как основной URL)
        job.result_path = job.preview_url or job.original_url

        job.status   = "done"
        job.progress = 100
        db.commit()

        logger.info(
            f"Job {job_id} done. "
            f"original={job.original_url[:60] if job.original_url else 'none'} "
            f"preview={job.preview_url[:60] if job.preview_url else 'none'} "
            f"thumb={job.thumb_url[:60] if job.thumb_url else 'none'}"
        )

    except Exception as e:
        logger.error(f"Error in postproc for job {job_id}: {e}")
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error  = str(e)[:400]
                db.commit()
                # Возврат гемов при ошибке постобработки
                if job.gems_cost and job.gems_cost > 0:
                    user = db.query(User).filter(User.id == job.user_id).first()
                    if user:
                        refund_gems(db, user, job.gems_cost, str(job.id))
        except Exception as inner:
            logger.error(f"Failed to mark job failed: {inner}")
    finally:
        db.close()


def callback(ch, method, properties, body):
    data   = json.loads(body)
    job_id = data.get("job_id")
    logger.info(f"Received job_id={job_id}")
    try:
        process_job(job_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    ensure_buckets()
    while True:
        try:
            params  = pika.URLParameters(settings.rabbitmq_url)
            conn    = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.queue_declare(queue=QUEUE_POSTPROC, durable=True)
            channel.queue_declare(queue=QUEUE_DLQ,      durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_POSTPROC, on_message_callback=callback)
            logger.info(f"Waiting for messages on {QUEUE_POSTPROC}")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection error: {e}, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
```

## Шаг Б5 — Проверить что media_processor возвращает правильный ключ

Открыть `api/services/media_processor.py`.

Найти строку в `process_video`:
```python
("preview_compressed_path", "preview_small.mp4", "video/mp4", create_preview_compressed),
```

Убедиться что ключ словаря именно `"preview_compressed_path"` (не `"preview_compressed"`).
Если отличается — поправить в `postproc_worker.py` соответственно.

## Шаг Б6 — Обновить роутер jobs чтобы отдавал новые поля

Открыть `api/routers/jobs.py`.

Найти эндпоинт `GET /jobs/:id` (getJobStatus).
Убедиться что он возвращает `JobStatusResponse` и что там есть новые поля.

Найти место где строится ответ, обычно что-то вроде:
```python
return JobStatusResponse(
    status=job.status,
    progress=job.progress,
    result_url=job.result_path,
    error=job.error,
)
```

Заменить на:
```python
return JobStatusResponse(
    status=job.status,
    progress=job.progress,
    result_url=job.result_path,      # превью (для обратной совместимости)
    preview_url=job.preview_url,
    thumb_url=job.thumb_url,
    original_url=job.original_url,
    error=job.error,
)
```

Найти эндпоинт `GET /jobs` (список джобов).
Убедиться что `JobOut` отдаётся через `model_config = {"from_attributes": True}` — тогда
новые поля подхватятся автоматически из ORM-модели. Если нет — добавить маппинг вручную.

## Шаг Б7 — Пересобрать и проверить

```bash
cd ~/Desktop/beckend_hyper_cut
docker compose down
docker compose up --build -d
docker compose logs worker-postproc -f --tail 30
# Ожидаем: "Waiting for messages on jobs.postproc"
```

Проверить FFmpeg есть в контейнере воркера:
```bash
docker compose exec worker-postproc ffmpeg -version | head -1
# Если нет: добавить в Dockerfile воркера: RUN apt-get install -y ffmpeg
```

Если FFmpeg отсутствует — открыть `api/workers/Dockerfile`, добавить строку:
```dockerfile
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```
И пересобрать: `docker compose up --build -d worker-postproc`

---

# ЧАСТЬ 2 — ФРОНТЕНД

Проект: `~/Desktop/hyper_cut`

## Шаг Ф1 — Обновить JobModel

Открыть `lib/models/job_model.dart`.

Добавить новые поля в класс:
```dart
final String? previewUrl;    // лёгкое видео для карточек
final String? thumbUrl;      // первый кадр (jpg)
final String? originalUrl;   // оригинал для полного просмотра
```

Обновить конструктор:
```dart
const JobModel({
  required this.id,
  required this.status,
  this.progress = 0,
  this.resultUrl,
  this.previewUrl,
  this.thumbUrl,
  this.originalUrl,
  this.error,
  this.gemsCost = 0,
  this.templateId,
  this.createdAt,
});
```

Обновить `fromJson`:
```dart
previewUrl:  (json['preview_url']  ?? json['result_path'])?.toString(),
thumbUrl:    json['thumb_url']?.toString(),
originalUrl: json['original_url']?.toString(),
```

Добавить геттер для удобства:
```dart
/// URL для воспроизведения в карточках (превью если есть, иначе оригинал)
String? get playbackUrl => previewUrl ?? resultUrl ?? originalUrl;

/// URL для полного просмотра (оригинал если есть)
String? get fullUrl => originalUrl ?? resultUrl;
```

## Шаг Ф2 — Создать виджет _JobVideoCard с автовоспроизведением

Открыть `lib/features/history/history_screen.dart`.

Заменить класс `_JobCard` полностью на следующий код:

```dart
class _JobCard extends StatefulWidget {
  const _JobCard({required this.job});
  final JobModel job;

  @override
  State<_JobCard> createState() => _JobCardState();
}

class _JobCardState extends State<_JobCard> {
  VideoPlayerController? _ctrl;
  bool _initialized = false;

  @override
  void initState() {
    super.initState();
    if (widget.job.isDone && widget.job.playbackUrl != null) {
      _initVideo();
    }
  }

  Future<void> _initVideo() async {
    final url = widget.job.playbackUrl!;
    try {
      final ctrl = VideoPlayerController.networkUrl(Uri.parse(url));
      await ctrl.initialize();
      ctrl.setLooping(true);
      ctrl.setVolume(0);
      await ctrl.play();
      if (mounted) setState(() { _ctrl = ctrl; _initialized = true; });
    } catch (_) {
      // показываем тамб если видео не загрузилось
    }
  }

  @override
  void dispose() {
    _ctrl?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final job = widget.job;
    final isProcessing = job.status == 'processing' || job.status == 'queued';

    return GestureDetector(
      onTap: job.isDone
          ? () => context.push(
                '/result?resultUrl=${Uri.encodeComponent(job.fullUrl ?? job.resultUrl ?? '')}',
              )
          : null,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Слой 1: тамб (пока видео не загрузилось)
            if (job.thumbUrl != null)
              Image.network(
                job.thumbUrl!,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) =>
                    const ColoredBox(color: AppColors.backgroundCard),
              )
            else
              const ColoredBox(color: AppColors.backgroundCard),

            // Слой 2: превью-видео (автовоспроизведение без звука)
            if (_initialized && _ctrl != null)
              RepaintBoundary(
                child: SizedBox.expand(
                  child: FittedBox(
                    fit: BoxFit.cover,
                    child: SizedBox(
                      width: _ctrl!.value.size.width,
                      height: _ctrl!.value.size.height,
                      child: VideoPlayer(_ctrl!),
                    ),
                  ),
                ),
              ),

            // Слой 3: оверлей — генерируется
            if (isProcessing) ...[
              Container(color: Colors.black.withOpacity(0.6)),
              Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(
                      color: AppColors.accentPurple,
                      strokeWidth: 3,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      job.status == 'queued' ? 'In Queue' : 'Generating...',
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (job.progress > 0) ...[
                      const SizedBox(height: 4),
                      Text(
                        '${job.progress}%',
                        style: GoogleFonts.inter(
                          fontSize: 11,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],

            // Слой 4: оверлей — ошибка
            if (job.isFailed) ...[
              Container(color: Colors.black.withOpacity(0.6)),
              Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline,
                        color: Colors.redAccent, size: 32),
                    const SizedBox(height: 8),
                    Text('Failed',
                        style: GoogleFonts.inter(
                            fontSize: 12, color: Colors.redAccent)),
                  ],
                ),
              ),
            ],

            // Слой 5: иконка play для готовых (пока видео грузится)
            if (job.isDone && !_initialized)
              const Center(
                child: Icon(Icons.play_circle_fill,
                    color: Colors.white54, size: 40),
              ),
          ],
        ),
      ),
    );
  }
}
```

Убедиться что в импортах файла есть:
```dart
import 'package:video_player/video_player.dart';
```

## Шаг Ф3 — Обновить ResultScreen для скачивания и шаринга

Открыть `lib/features/create/result_screen.dart`.

### 3.1 Добавить импорты в начало файла:
```dart
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
```

Если `share_plus` и `path_provider` не в `pubspec.yaml` — добавить:
```bash
cd ~/Desktop/hyper_cut
flutter pub add share_plus path_provider
```

### 3.2 Обновить конструктор ResultScreen:
```dart
class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key, this.resultUrl, this.originalUrl});

  final String? resultUrl;    // превью или что есть
  final String? originalUrl;  // оригинал для скачивания

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}
```

### 3.3 Добавить методы скачивания и шаринга в `_ResultScreenState`:

```dart
bool _downloading = false;

Future<void> _downloadVideo() async {
  final url = widget.originalUrl ?? widget.resultUrl;
  if (url == null) return;

  setState(() => _downloading = true);
  try {
    final resp = await http.get(Uri.parse(url));
    final dir  = await getApplicationDocumentsDirectory();
    final path = '${dir.path}/hypcut_${DateTime.now().millisecondsSinceEpoch}.mp4';
    await File(path).writeAsBytes(resp.bodyBytes);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Video saved to device')),
      );
    }
  } catch (e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Download failed: $e')),
      );
    }
  } finally {
    if (mounted) setState(() => _downloading = false);
  }
}

Future<void> _shareVideo() async {
  final url = widget.originalUrl ?? widget.resultUrl;
  if (url == null) return;

  try {
    // Скачать во временный файл и расшарить
    final resp = await http.get(Uri.parse(url));
    final tmp  = await getTemporaryDirectory();
    final path = '${tmp.path}/share_video.mp4';
    await File(path).writeAsBytes(resp.bodyBytes);
    await Share.shareXFiles([XFile(path)], text: 'Check out my HypeCut video!');
  } catch (e) {
    // Fallback — скопировать ссылку
    await Clipboard.setData(ClipboardData(text: url));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Link copied to clipboard')),
      );
    }
  }
}
```

### 3.4 Обновить кнопки в `_buildBottomSection` или bottom actions:

Найти кнопки внизу ResultScreen (Copy Link / Create More) и заменить на три кнопки:

```dart
Row(
  children: [
    // Скачать
    Expanded(
      child: GestureDetector(
        onTap: _downloading ? null : _downloadVideo,
        child: Container(
          height: 52,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.15),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withOpacity(0.3)),
          ),
          child: _downloading
              ? const Center(
                  child: SizedBox(
                    width: 20, height: 20,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  ),
                )
              : Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.download, color: Colors.white, size: 18),
                    const SizedBox(width: 6),
                    Text('Save',
                        style: GoogleFonts.inter(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Colors.white)),
                  ],
                ),
        ),
      ),
    ),
    const SizedBox(width: 8),
    // Поделиться
    Expanded(
      child: GestureDetector(
        onTap: _shareVideo,
        child: Container(
          height: 52,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.15),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withOpacity(0.3)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.share, color: Colors.white, size: 18),
              const SizedBox(width: 6),
              Text('Share',
                  style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.white)),
            ],
          ),
        ),
      ),
    ),
    const SizedBox(width: 8),
    // Создать ещё
    Expanded(
      child: GestureDetector(
        onTap: () => context.go('/home'),
        child: Container(
          height: 52,
          decoration: BoxDecoration(
            color: AppColors.accentPurpleLight,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.add, color: Colors.white, size: 18),
              const SizedBox(width: 6),
              Text('More',
                  style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.white)),
            ],
          ),
        ),
      ),
    ),
  ],
),
```

## Шаг Ф4 — Обновить Router чтобы передавал original_url

Открыть `lib/core/router/*.dart` (файл с GoRouter).

Найти роут `/result` и обновить:
```dart
GoRoute(
  path: '/result',
  builder: (context, state) => ResultScreen(
    resultUrl:   state.uri.queryParameters['resultUrl'],
    originalUrl: state.uri.queryParameters['originalUrl'],
  ),
),
```

Найти в `_JobCard` строку навигации и добавить `originalUrl`:
```dart
context.push(
  '/result'
  '?resultUrl=${Uri.encodeComponent(job.fullUrl ?? job.resultUrl ?? '')}'
  '&originalUrl=${Uri.encodeComponent(job.originalUrl ?? job.resultUrl ?? '')}',
)
```

## Шаг Ф5 — Финальная проверка

```bash
cd ~/Desktop/hyper_cut

# Анализ
flutter analyze
# Должно быть 0 issues

# Запуск
flutter run -d R5CY23GXQ2D
```

Проверить сценарий вручную:
1. Открыть History → My Works
2. Завершённые джобы должны показывать автовоспроизведение превью без звука
3. Тап на карточку → ResultScreen с оригинальным видео
4. Кнопка Save → видео сохраняется на устройство
5. Кнопка Share → открывается системный шарер с видео-файлом

---

# Ожидаемый результат

**Бэкенд:**
- [ ] Поля `preview_url`, `thumb_url`, `original_url` добавлены в таблицу `jobs`
- [ ] `postproc_worker` скачивает оригинал → сохраняет в MinIO → генерирует превью через FFmpeg
- [ ] `GET /jobs` и `GET /jobs/:id` возвращают все три URL
- [ ] `result_path` содержит превью-URL (для обратной совместимости)

**Фронтенд:**
- [ ] `JobModel` парсит `preview_url`, `thumb_url`, `original_url`
- [ ] В History карточки показывают тамб сразу, потом автовоспроизводят превью без звука
- [ ] Тап на карточку открывает ResultScreen с оригиналом
- [ ] В ResultScreen работают кнопки Save и Share
