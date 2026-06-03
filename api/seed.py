"""Seed initial data: admin user, categories, templates, admin_config, gem_packages, subscription_plans."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.database import SessionLocal
from core.security import hash_password
from core.config import get_settings
from models.user import User
from models.template import Template
from models.category import Category
from models.admin_config import AdminConfig
from models.gem_package import GemPackage
from models.subscription_plan import SubscriptionPlan

settings = get_settings()


def seed():
    db = SessionLocal()
    try:
        # Admin user
        admin = db.query(User).filter(User.email == settings.admin_email).first()
        if not admin:
            admin = User(
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"Created admin: {settings.admin_email}")
        else:
            print(f"Admin already exists: {settings.admin_email}")

        # Categories
        category_names = ["Couples", "Dance Floor", "Goddess Aura", "Home & Cozy"]
        for i, name in enumerate(category_names):
            if not db.query(Category).filter(Category.name == name).first():
                db.add(Category(name=name, order=i))
                print(f"Created category: {name}")
        db.commit()

        # Templates
        template_data = [
            ("Romantic Sunset", "A beautiful sunset template for couples"),
            ("Club Vibes", "High energy dance floor visuals"),
            ("Golden Hour Glow", "Warm tones and goddess aesthetic"),
            ("Cozy Morning", "Soft home aesthetics for cozy content"),
            ("Neon Nights", "Electric neon dance visuals"),
        ]
        for title, desc in template_data:
            if not db.query(Template).filter(Template.title == title).first():
                db.add(Template(title=title, description=desc, created_by=admin.id))
                print(f"Created template: {title}")
        db.commit()

        # Admin config
        config_defaults = {
            "STUB_MODE": "true",
            "STUB_LATENCY_MS": "10000",
            "STUB_SUCCESS_RATE": "0.8",
            "AI_ENDPOINT": "",
            "AI_TOKEN": "",
        }
        for key, value in config_defaults.items():
            if not db.query(AdminConfig).filter(AdminConfig.key == key).first():
                db.add(AdminConfig(key=key, value=value, updated_by=admin.id))
                print(f"Set config: {key}={value}")
        db.commit()

        # Gem packages
        gem_data = [
            dict(gems_amount=800,   bonus_gems=0,    price=679.99,   label="Starter",      is_popular=False, order=0),
            dict(gems_amount=2300,  bonus_gems=300,  price=1599.99,  label=None,            is_popular=False, order=1),
            dict(gems_amount=3300,  bonus_gems=500,  price=2099.99,  label=None,            is_popular=False, order=2),
            dict(gems_amount=6000,  bonus_gems=1000, price=3699.99,  label=None,            is_popular=False, order=3),
            dict(gems_amount=10000, bonus_gems=2000, price=5249.99,  label="Most Popular",  is_popular=True,  order=4),
        ]
        for g in gem_data:
            exists = db.query(GemPackage).filter(GemPackage.gems_amount == g["gems_amount"]).first()
            if not exists:
                db.add(GemPackage(**g))
                print(f"Created gem package: {g['gems_amount']} gems")
        db.commit()

        # Subscription plans
        plan_data = [
            dict(name="Weekly VIP",   tier="vip",  period="weekly",   price=419.99,  bonus_gems=400,  discount_percent=0,  order=0),
            dict(name="Yearly VIP",   tier="vip",  period="yearly",   price=2099.99, bonus_gems=3000, discount_percent=50, order=1),
            dict(name="Weekly SVIP",  tier="svip", period="weekly",   price=529.99,  bonus_gems=600,  discount_percent=0,  order=2),
            dict(name="Lifetime SVIP",tier="svip", period="lifetime", price=3699.99, bonus_gems=6000, discount_percent=0,  order=3),
        ]
        for p in plan_data:
            exists = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == p["name"]).first()
            if not exists:
                db.add(SubscriptionPlan(**p))
                print(f"Created subscription plan: {p['name']}")
        db.commit()

        print("\nSeed completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
