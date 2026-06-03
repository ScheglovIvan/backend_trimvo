#!/usr/bin/env python3
import os
import sys
import time
import random
import requests

API_BASE = "http://localhost:8000/v1"
CONTENT_DIR = "/Users/gennadij/Desktop/hypercut_content"
ADMIN_EMAIL = "admin@hypercut.com"
ADMIN_PASSWORD = "admin123"
IGNORE_DIRS = {"trends"}
IGNORE_FILES = {"welcome.mp4", ".DS_Store"}

CATEGORY_ORDER = {
    "Couples": 0,
    "Dance Floor": 1,
    "Goddes Aura": 2,
    "High Energy": 3,
    "Home & Cozy": 4,
    "Magic Makeover": 5,
}

def get_token():
    r = requests.post(f"{API_BASE}/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    })
    r.raise_for_status()
    token = r.json()["access_token"]
    print(f"Logged in as {ADMIN_EMAIL}")
    return token

def hdrs(token):
    return {"Authorization": f"Bearer {token}"}

def delete_all_templates(token):
    print("\nDeleting all templates...")
    r = requests.get(f"{API_BASE}/admin/templates?per_page=200", headers=hdrs(token))
    items = r.json().get("items", [])
    for t in items:
        requests.delete(f"{API_BASE}/admin/templates/{t['id']}", headers=hdrs(token))
        print(f"  Deleted: {t['title']}")
    print(f"  Total deleted: {len(items)}")

def delete_all_categories(token):
    print("\nDeleting all categories...")
    r = requests.get(f"{API_BASE}/admin/categories", headers=hdrs(token))
    cats = r.json() if isinstance(r.json(), list) else []
    for c in cats:
        requests.delete(f"{API_BASE}/admin/categories/{c['id']}", headers=hdrs(token))
        print(f"  Deleted: {c['name']}")
    print(f"  Total deleted: {len(cats)}")

def create_categories(token):
    print("\nCreating categories...")
    categories = {}
    for name, order in CATEGORY_ORDER.items():
        r = requests.post(f"{API_BASE}/admin/categories",
            headers=hdrs(token),
            json={"name": name, "order": order},
        )
        cat = r.json()
        categories[name] = cat["id"]
        print(f"  Created: {name} (id={cat['id']})")
    return categories

def make_title(filename):
    name = os.path.splitext(filename)[0]
    parts = name.split("_")
    number = parts[0] if parts else name
    # Remove batch prefix
    if number == "batch":
        number = name[:20]
    return f"Template {number}"

def upload_template(token, video_path, title, plays, likes, photo_slots):
    with open(video_path, "rb") as f:
        r = requests.post(
            f"{API_BASE}/admin/templates",
            headers=hdrs(token),
            data={
                "title": title,
                "plays": str(plays),
                "likes": str(likes),
                "gems_cost": "200",
                "photo_slots": str(photo_slots),
            },
            files={"video": (os.path.basename(video_path), f, "video/mp4")},
        )
    if r.status_code not in (200, 201):
        print(f"  FAILED {title}: {r.status_code} {r.text[:200]}")
        return None
    return r.json()

def assign_to_category(token, category_id, template_id):
    requests.post(
        f"{API_BASE}/admin/categories/{category_id}/templates",
        headers=hdrs(token),
        json={"template_ids": [template_id]},
    )

def main():
    token = get_token()

    delete_all_templates(token)
    delete_all_categories(token)
    categories = create_categories(token)

    uploaded = 0
    failed = 0

    for folder_name in sorted(os.listdir(CONTENT_DIR)):
        folder_path = os.path.join(CONTENT_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue
        if folder_name in IGNORE_DIRS:
            print(f"\nSkipping: {folder_name}")
            continue

        category_id = categories.get(folder_name)
        if not category_id:
            print(f"\nNo category for folder: {folder_name}, skipping")
            continue

        photo_slots = 2 if folder_name == "Couples" else 1
        print(f"\nProcessing: {folder_name}")

        videos = [
            f for f in sorted(os.listdir(folder_path))
            if f.endswith(".mp4") and f not in IGNORE_FILES
        ]

        for filename in videos:
            video_path = os.path.join(folder_path, filename)
            title = make_title(filename)
            plays = random.randint(9000, 25000)
            likes = random.randint(500, 1800)

            print(f"  Uploading: {filename} -> {title} (plays={plays}, likes={likes})")

            template = upload_template(token, video_path, title, plays, likes, photo_slots)
            if not template:
                failed += 1
                continue

            assign_to_category(token, category_id, template["id"])
            print(f"  OK: {template['id']}")
            uploaded += 1
            time.sleep(0.3)

    print(f"\n{'='*50}")
    print(f"Uploaded: {uploaded}, Failed: {failed}")

    # Verification
    print("\nVerification (immediate - thumbnails still processing)...")
    r = requests.get(f"{API_BASE}/admin/templates?per_page=200", headers=hdrs(token))
    templates = r.json().get("items", [])
    print(f"  Total templates in DB: {len(templates)}")

    for status in ["ready", "processing", "failed", "queued"]:
        count = len([t for t in templates if t.get("status") == status])
        if count:
            print(f"  Status {status}: {count}")

    r2 = requests.get(f"{API_BASE}/admin/categories", headers=hdrs(token))
    cats = r2.json() if isinstance(r2.json(), list) else []
    print(f"\n  Categories ({len(cats)}):")
    for c in cats:
        r3 = requests.get(
            f"{API_BASE}/admin/categories/{c['id']}/templates",
            headers=hdrs(token),
        )
        cat_templates = r3.json() if isinstance(r3.json(), list) else []
        print(f"    {c['name']}: {len(cat_templates)} templates")

if __name__ == "__main__":
    main()
