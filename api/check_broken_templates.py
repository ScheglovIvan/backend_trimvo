"""
Диагностика битых шаблонов: проверяет какие шаблоны имеют пустые
thumb_path / preview_path / gif_path, неактивны, или имеют статус != ready.
Запуск внутри контейнера:
  docker compose exec api python check_broken_templates.py
"""
from core.database import SessionLocal
from models.template import Template


def main():
    db = SessionLocal()
    try:
        templates = db.query(Template).all()
        print(f"Всего шаблонов в БД: {len(templates)}\n")

        broken = []
        for t in templates:
            issues = []
            if not t.thumb_path:
                issues.append("НЕТ thumb_path")
            if not t.preview_path:
                issues.append("НЕТ preview_path")
            if not t.gif_path:
                issues.append("НЕТ gif_path")
            if not t.is_active:
                issues.append("is_active=False")
            if t.status != "ready":
                issues.append(f"status={t.status}")

            if issues:
                broken.append((t, issues))

        if not broken:
            print("✅ Все шаблоны в порядке (все пути заполнены, активны, ready)")
        else:
            print(f"⚠️  Найдено битых шаблонов: {len(broken)}\n")
            for t, issues in broken:
                print(f"  id={t.id}")
                print(f"    title: {t.title}")
                print(f"    проблемы: {', '.join(issues)}")
                print(f"    thumb_path: {t.thumb_path}")
                print(f"    preview_path: {t.preview_path}")
                print(f"    gif_path: {t.gif_path}")
                print()
    finally:
        db.close()


if __name__ == "__main__":
    main()
