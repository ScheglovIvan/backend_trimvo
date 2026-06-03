#!/usr/bin/env python3
"""
Fix categories and reassign templates based on hypercut_content folders.
"""
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from sqlalchemy import text
from core.database import SessionLocal
from models.template import Template
from models.category import Category, CategoryTemplate
from models.trend import Trend

CONTENT_DIR = "/Users/gennadij/Desktop/hypercut_content"
IGNORE_DIRS = {"trends"}
IGNORE_FILES = {"welcome.mp4", ".DS_Store"}

# Маппинг папка → правильное название категории
FOLDER_TO_CATEGORY = {
    "Couples":       "Couples",
    "Dance Floor":   "Dance Floor",
    "Goddes Aura":   "Goddess Aura",
    "High Energy":   "High Energy",
    "Home & Cozy":   "Home & Cozy",
    "Magic Makeover":"Magic Makeover",
}

CATEGORY_ORDER = {
    "Couples":        0,
    "Dance Floor":    1,
    "Goddess Aura":   2,
    "High Energy":    3,
    "Home & Cozy":    4,
    "Magic Makeover": 5,
}

# Файлы из папки trends → добавить в тренды
TRENDS_DIR = os.path.join(CONTENT_DIR, "trends")

def make_title(filename):
    name = os.path.splitext(filename)[0]
    parts = name.split("_")
    number = parts[0] if parts else name
    if number == "batch":
        number = name[:20]
    return f"Template {number}"


def main():
    db = SessionLocal()
    try:
        # ── Шаг 1: Удалить дублированные категории ────────────────────────
        print("Step 1: Fix duplicate and misnamed categories...")

        all_cats = db.query(Category).all()
        print(f"  Found {len(all_cats)} categories:")
        for c in all_cats:
            ct_count = db.query(CategoryTemplate).filter(
                CategoryTemplate.category_id == c.id
            ).count()
            print(f"    '{c.name}' (id={c.id}, templates={ct_count})")

        # Удалить пустые дубликаты и категории с опечатками
        cats_to_delete = []
        seen_names = {}

        # Сначала исправить опечатку в Goddes Aura → Goddess Aura
        for c in all_cats:
            if c.name == "Goddes Aura":
                c.name = "Goddess Aura"
                print(f"  Renamed: 'Goddes Aura' → 'Goddess Aura'")

        db.commit()

        # Найти и удалить дубликаты (оставить тот у которого больше шаблонов)
        all_cats = db.query(Category).all()
        name_to_cats = {}
        for c in all_cats:
            if c.name not in name_to_cats:
                name_to_cats[c.name] = []
            name_to_cats[c.name].append(c)

        for name, cats in name_to_cats.items():
            if len(cats) > 1:
                # Оставить тот у которого больше шаблонов
                cats_with_count = []
                for c in cats:
                    count = db.query(CategoryTemplate).filter(
                        CategoryTemplate.category_id == c.id
                    ).count()
                    cats_with_count.append((c, count))
                cats_with_count.sort(key=lambda x: x[1], reverse=True)

                keep = cats_with_count[0][0]
                print(f"  Keeping '{name}' (id={keep.id}, "
                      f"templates={cats_with_count[0][1]})")

                for c, count in cats_with_count[1:]:
                    print(f"  Deleting duplicate '{name}' "
                          f"(id={c.id}, templates={count})")
                    db.delete(c)

        db.commit()

        # Обновить order для категорий
        all_cats = db.query(Category).all()
        for c in all_cats:
            if c.name in CATEGORY_ORDER:
                c.order = CATEGORY_ORDER[c.name]
        db.commit()

        all_cats = db.query(Category).order_by(Category.order).all()
        print(f"\n  Categories after fix ({len(all_cats)}):")
        for c in all_cats:
            print(f"    [{c.order}] '{c.name}' (id={c.id})")

        # ── Шаг 2: Очистить все назначения категорий ──────────────────────
        print("\nStep 2: Clear all category_templates assignments...")
        deleted = db.query(CategoryTemplate).delete()
        db.commit()
        print(f"  Cleared {deleted} assignments")

        # ── Шаг 3: Раскидать шаблоны по категориям из папок ───────────────
        print("\nStep 3: Reassign templates to categories based on folders...")

        # Построить маппинг: title → template
        all_templates = db.query(Template).all()
        title_to_template = {t.title: t for t in all_templates}
        print(f"  Total templates: {len(all_templates)}")

        # Построить маппинг: имя категории → объект
        cat_by_name = {c.name: c for c in all_cats}

        assigned = 0
        not_found_templates = []
        not_found_categories = []
        seen_pairs = set()  # in-memory dedup: (category_id, template_id)

        for folder_name in sorted(os.listdir(CONTENT_DIR)):
            folder_path = os.path.join(CONTENT_DIR, folder_name)
            if not os.path.isdir(folder_path):
                continue
            if folder_name in IGNORE_DIRS:
                continue

            category_name = FOLDER_TO_CATEGORY.get(folder_name)
            if not category_name:
                print(f"  No mapping for folder: {folder_name}")
                continue

            cat = cat_by_name.get(category_name)
            if not cat:
                print(f"  Category not found: {category_name}")
                not_found_categories.append(category_name)
                continue

            print(f"\n  Folder: {folder_name} → Category: {category_name}")

            videos = [
                f for f in sorted(os.listdir(folder_path))
                if f.endswith(".mp4") and f not in IGNORE_FILES
            ]

            folder_assigned = 0
            order_idx = 0
            for filename in videos:
                title = make_title(filename)
                template = title_to_template.get(title)
                if not template:
                    not_found_templates.append(
                        f"{folder_name}/{filename} → {title}"
                    )
                    continue

                pair = (cat.id, template.id)
                if pair in seen_pairs:
                    print(f"    Skipping duplicate: {filename} → {title}")
                    continue
                seen_pairs.add(pair)

                db.add(CategoryTemplate(
                    category_id=cat.id,
                    template_id=template.id,
                    order=order_idx,
                ))
                order_idx += 1
                folder_assigned += 1
                assigned += 1

            db.commit()
            print(f"    Assigned {folder_assigned}/{len(videos)} templates")

        print(f"\n  Total assigned: {assigned}")

        if not_found_templates:
            print(f"\n  Templates not found in DB ({len(not_found_templates)}):")
            for t in not_found_templates[:10]:
                print(f"    {t}")

        # ── Шаг 4: Добавить тренды из папки trends ────────────────────────
        print("\nStep 4: Set up trends from trends folder...")

        # Удалить старые тренды
        old_trends = db.query(Trend).delete()
        db.commit()
        print(f"  Cleared {old_trends} old trends")

        if os.path.isdir(TRENDS_DIR):
            trend_videos = [
                f for f in sorted(os.listdir(TRENDS_DIR))
                if f.endswith(".mp4") and f not in IGNORE_FILES
            ]
            print(f"  Found {len(trend_videos)} trend videos")

            trend_order = 0
            for filename in trend_videos:
                title = make_title(filename)
                template = title_to_template.get(title)
                if not template:
                    print(f"  Trend template not found: {title}")
                    continue

                db.add(Trend(
                    template_id=template.id,
                    order=trend_order,
                ))
                trend_order += 1
                print(f"  Added trend: {title}")

            db.commit()
            print(f"  Total trends: {trend_order}")
        else:
            print("  trends folder not found")

        # ── Шаг 5: Верификация ─────────────────────────────────────────────
        print("\nStep 5: Verification...")

        result = db.execute(text("""
            SELECT c.name, COUNT(ct.template_id) as cnt
            FROM categories c
            LEFT JOIN category_templates ct ON ct.category_id = c.id
            GROUP BY c.name, c.order
            ORDER BY c.order
        """)).fetchall()

        print("\n  Category → Templates:")
        for row in result:
            print(f"    {row[0]}: {row[1]} templates")

        trend_count = db.query(Trend).count()
        print(f"\n  Trends: {trend_count}")

        total_assigned = db.query(CategoryTemplate).count()
        print(f"  Total category assignments: {total_assigned}")

        # Шаблоны без категории
        unassigned = db.execute(text("""
            SELECT COUNT(*) FROM templates t
            WHERE NOT EXISTS (
                SELECT 1 FROM category_templates ct
                WHERE ct.template_id = t.id
            )
        """)).scalar()
        print(f"  Templates without category: {unassigned}")

        print("\nDone!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
